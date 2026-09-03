"""FastAPI application exposing portfolio analytics to the React client."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import providers, service, warehouse
from app.config import get_settings
from app.reference import search as reference_search
from app.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse, SearchResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create the warehouse tables on boot; the API still serves without them."""
    try:
        warehouse.initialize()
    except Exception as exc:  # noqa: BLE001 - analytics work without the warehouse
        log.warning("Warehouse initialization failed: %s", exc)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Portfolio Analysis API",
    version="0.1.0",
    description=(
        "Market data ingestion, portfolio risk and diversification analytics, "
        "backed by DuckDB and dbt."
    ),
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    available = providers.availability()
    active = next((name for name, ok in available.items() if ok), "none")
    return HealthResponse(
        status="ok",
        providers=available,
        active_provider=active,
        warehouse=warehouse.stats(),
    )


@app.get("/api/search", response_model=list[SearchResult])
def search(q: str = Query(..., min_length=1, max_length=32)) -> list[SearchResult]:
    """Ticker autocomplete, served from the static reference universe."""
    return [
        SearchResult(
            ticker=s.ticker, name=s.name, sector=s.sector, asset_class=s.asset_class
        )
        for s in reference_search(q)
    ]


@app.post("/api/portfolio/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Fetch data, compute analytics and return the full portfolio picture."""
    try:
        return service.analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except providers.ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


class DbtRequest(BaseModel):
    command: str = "build"
    select: str | None = None


@app.post("/api/warehouse/dbt")
def run_dbt(request: DbtRequest) -> dict:
    """Rebuild the dbt marts from whatever raw data has been landed so far."""
    if request.command not in {"build", "run", "test", "seed", "compile"}:
        raise HTTPException(status_code=400, detail=f"Unsupported dbt command: {request.command}")
    return warehouse.run_dbt(request.command, request.select)


@app.get("/api/warehouse/tables")
def tables() -> list[dict]:
    return warehouse.list_tables()


class QueryRequest(BaseModel):
    sql: str
    limit: int = 500


@app.post("/api/warehouse/query")
def run_query(request: QueryRequest) -> dict:
    """Read-only SQL against the warehouse, for exploring the dbt marts."""
    try:
        rows = warehouse.query(request.sql, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}") from exc
    return {"rows": rows, "count": len(rows)}
