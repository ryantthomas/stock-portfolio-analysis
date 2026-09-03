"""DuckDB warehouse: the landing zone that dbt builds on top of.

The API writes raw, unmodelled data here -- prices as fetched, security
metadata as returned by the provider, and a snapshot of every portfolio the
user analyzes. dbt then owns all transformation from `raw_*` through staging
and intermediate models into the `mart_*` tables the UI reads.

Splitting it this way means analytics logic lives in version-controlled SQL
that can be tested and documented, rather than being buried in Python.
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from app.config import get_settings
from app.schemas import SecurityMeta

log = logging.getLogger(__name__)

RAW_SCHEMA = "raw"

_DDL = f"""
CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA};

CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.prices (
    ticker        VARCHAR NOT NULL,
    price_date    DATE    NOT NULL,
    adj_close     DOUBLE  NOT NULL,
    provider      VARCHAR NOT NULL,
    loaded_at     TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.securities (
    ticker          VARCHAR NOT NULL,
    name            VARCHAR,
    sector          VARCHAR,
    industry        VARCHAR,
    country         VARCHAR,
    asset_class     VARCHAR,
    currency        VARCHAR,
    market_cap      DOUBLE,
    pe_ratio        DOUBLE,
    dividend_yield  DOUBLE,
    beta            DOUBLE,
    provider        VARCHAR NOT NULL,
    loaded_at       TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.portfolio_holdings (
    portfolio_id  VARCHAR NOT NULL,
    label         VARCHAR,
    ticker        VARCHAR NOT NULL,
    weight        DOUBLE  NOT NULL,
    benchmark     VARCHAR,
    created_at    TIMESTAMP NOT NULL
);

-- Index on the columns every dbt staging model filters or joins on.
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date
    ON {RAW_SCHEMA}.prices (ticker, price_date);
"""


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    path = Path(settings.duckdb_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if read_only and not path.exists():
        # DuckDB refuses to open a missing file read-only; create it first.
        duckdb.connect(str(path)).close()
    return duckdb.connect(str(path), read_only=read_only)


def initialize() -> None:
    """Create the raw schema and tables if they do not exist yet."""
    con = connect()
    try:
        con.execute(_DDL)
    finally:
        con.close()


def load_prices(prices: pd.DataFrame, provider: str) -> int:
    """Upsert a wide price panel into `raw.prices` (long format).

    Existing rows for the same (ticker, date) are replaced so a refetch
    corrects rather than duplicates history.
    """
    if prices is None or prices.empty:
        return 0

    long = (
        prices.rename_axis("price_date")
        .reset_index()
        .melt(id_vars="price_date", var_name="ticker", value_name="adj_close")
        .dropna(subset=["adj_close"])
    )
    if long.empty:
        return 0

    long["price_date"] = pd.to_datetime(long["price_date"]).dt.date
    long["provider"] = provider
    long["loaded_at"] = datetime.now(timezone.utc)

    initialize()
    con = connect()
    try:
        con.register("incoming_prices", long)
        con.execute(
            f"""
            DELETE FROM {RAW_SCHEMA}.prices
            WHERE (ticker, price_date) IN (
                SELECT ticker, price_date FROM incoming_prices
            )
            """
        )
        con.execute(
            f"""
            INSERT INTO {RAW_SCHEMA}.prices
                (ticker, price_date, adj_close, provider, loaded_at)
            SELECT ticker, price_date, adj_close, provider, loaded_at
            FROM incoming_prices
            """
        )
        con.unregister("incoming_prices")
    finally:
        con.close()
    return len(long)


def load_securities(metadata: dict[str, SecurityMeta], provider: str) -> int:
    """Replace security metadata rows for the given tickers."""
    if not metadata:
        return 0

    rows = []
    now = datetime.now(timezone.utc)
    for ticker, meta in metadata.items():
        record = meta.model_dump()
        record["ticker"] = ticker
        record["provider"] = provider
        record["loaded_at"] = now
        rows.append(record)

    frame = pd.DataFrame(rows)

    initialize()
    con = connect()
    try:
        con.register("incoming_securities", frame)
        con.execute(
            f"""
            DELETE FROM {RAW_SCHEMA}.securities
            WHERE ticker IN (SELECT ticker FROM incoming_securities)
            """
        )
        con.execute(
            f"""
            INSERT INTO {RAW_SCHEMA}.securities
            SELECT ticker, name, sector, industry, country, asset_class, currency,
                   market_cap, pe_ratio, dividend_yield, beta, provider, loaded_at
            FROM incoming_securities
            """
        )
        con.unregister("incoming_securities")
    finally:
        con.close()
    return len(rows)


def save_portfolio(
    weights: dict[str, float], benchmark: str, label: str | None = None
) -> str:
    """Persist a portfolio snapshot so dbt models can analyze it. Returns its id."""
    if not weights:
        return ""

    portfolio_id = uuid.uuid4().hex[:12]
    frame = pd.DataFrame(
        {
            "portfolio_id": portfolio_id,
            "label": label or "unnamed",
            "ticker": list(weights),
            "weight": list(weights.values()),
            "benchmark": benchmark,
            "created_at": datetime.now(timezone.utc),
        }
    )

    initialize()
    con = connect()
    try:
        con.register("incoming_holdings", frame)
        con.execute(
            f"INSERT INTO {RAW_SCHEMA}.portfolio_holdings SELECT * FROM incoming_holdings"
        )
        con.unregister("incoming_holdings")
    finally:
        con.close()
    return portfolio_id


def run_dbt(command: str = "build", select: str | None = None) -> dict[str, object]:
    """Invoke the dbt project against the same DuckDB file.

    dbt is an optional dependency; when it is not installed the API keeps
    working and simply reports that the marts were not refreshed.
    """
    settings = get_settings()
    project_dir = Path(settings.dbt_project_dir)
    if not project_dir.exists():
        return {"ok": False, "reason": f"dbt project not found at {project_dir}"}

    args = [
        "dbt",
        command,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
    ]
    if select:
        args += ["--select", select]

    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            args,
            capture_output=True,
            text=True,
            timeout=600,
            env={"DUCKDB_PATH": str(settings.duckdb_path), **_env()},
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "reason": "dbt is not installed. Install with: pip install -e 'api[dbt]'",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "dbt run timed out after 600s"}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-4000:],
    }


def _env() -> dict[str, str]:
    import os

    return dict(os.environ)


def list_tables() -> list[dict[str, str]]:
    """Every table and view visible in the warehouse, raw and dbt-built alike."""
    con = connect(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
    except duckdb.Error as exc:
        log.warning("Could not list warehouse tables: %s", exc)
        return []
    finally:
        con.close()
    return [{"schema": r[0], "name": r[1], "type": r[2]} for r in rows]


def query(sql: str, limit: int = 1000) -> list[dict]:
    """Run a read-only SELECT against the warehouse.

    The connection is opened read-only, so DuckDB itself rejects any statement
    that would write -- the string check below just returns a clearer error.
    """
    stripped = sql.strip().rstrip(";")
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only SELECT/WITH statements are allowed")

    con = connect(read_only=True)
    try:
        frame = con.execute(f"SELECT * FROM ({stripped}) LIMIT {int(limit)}").fetchdf()
    finally:
        con.close()
    return frame.to_dict(orient="records")


def stats() -> dict[str, object]:
    """Summary of what the warehouse currently holds, for the health endpoint."""
    settings = get_settings()
    path = Path(settings.duckdb_path)
    if not path.exists():
        return {"exists": False, "path": str(path)}

    con = connect(read_only=True)
    try:
        tables = {t["schema"] + "." + t["name"] for t in list_tables()}
        out: dict[str, object] = {"exists": True, "path": str(path), "tables": len(tables)}
        if f"{RAW_SCHEMA}.prices" in tables:
            row = con.execute(
                f"""
                SELECT COUNT(*), COUNT(DISTINCT ticker),
                       MIN(price_date), MAX(price_date)
                FROM {RAW_SCHEMA}.prices
                """
            ).fetchone()
            out |= {
                "price_rows": row[0],
                "tickers": row[1],
                "history_start": str(row[2]) if row[2] else None,
                "history_end": str(row[3]) if row[3] else None,
            }
        out["marts"] = sorted(t for t in tables if "mart_" in t)
        return out
    except duckdb.Error as exc:
        return {"exists": True, "path": str(path), "error": str(exc)}
    finally:
        con.close()
