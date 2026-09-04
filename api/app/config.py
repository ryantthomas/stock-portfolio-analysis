"""Runtime configuration, sourced from environment variables (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="PORTFOLIO_", extra="ignore"
    )

    # Where the DuckDB warehouse file lives. dbt reads the same file.
    duckdb_path: Path = REPO_ROOT / "data" / "warehouse.duckdb"

    # Root of the dbt project, used when the API triggers a `dbt build`.
    dbt_project_dir: Path = REPO_ROOT / "dbt" / "portfolio"

    # Provider preference order. "auto" walks the chain until one succeeds.
    provider: str = "auto"

    # Origins allowed to call the API from a browser. Irrelevant when the API
    # also serves the frontend, since everything is then one origin.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Built frontend to serve. When this directory exists the API serves the
    # SPA itself, so a deployment is a single container on a single origin.
    static_dir: Path = REPO_ROOT / "web" / "dist"

    # The warehouse endpoints run arbitrary SQL and shell out to dbt. They are
    # operator tools, not user-facing features, so they are off unless
    # explicitly enabled -- a public deployment must leave this False.
    enable_warehouse_api: bool = False

    # Whether an analysis saves a snapshot of the portfolio. Useful locally for
    # building dbt models; on a public site it accumulates unbounded rows from
    # anonymous visitors, so deployments generally want it off.
    persist_portfolios: bool = True

    # Requests per minute per client IP for the analysis endpoint. 0 disables
    # the limit. In-process only -- see the note in main.py.
    rate_limit_per_minute: int = 30

    # Price history cached on disk for this many minutes before refetching.
    cache_ttl_minutes: int = 60

    # Risk-free rate used for Sharpe ratios, as an annualized decimal.
    risk_free_rate: float = 0.042

    # Trading days per year, used to annualize daily statistics.
    trading_days: int = 252

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
