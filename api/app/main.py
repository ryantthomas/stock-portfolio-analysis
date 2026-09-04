"""FastAPI application exposing portfolio analytics to the React client."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import providers, service, warehouse
from app.config import get_settings
from app.ratelimit import RateLimiter
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

limiter = RateLimiter(limit=settings.rate_limit_per_minute)


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    Behind a proxy the socket address is the proxy, so the first hop in
    X-Forwarded-For is used when present. That header is client-controlled and
    trivially spoofed, so this throttles honest traffic and accidental loops --
    it is not a defence against a determined attacker. Put a real limiter in
    the proxy for that.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_warehouse_api() -> None:
    """Refuse the operator-only endpoints unless explicitly enabled."""
    if not settings.enable_warehouse_api:
        raise HTTPException(
            status_code=404,
            detail=(
                "The warehouse endpoints are disabled. They run arbitrary SQL and "
                "invoke dbt, so they are opt-in: set PORTFOLIO_ENABLE_WAREHOUSE_API=true "
                "to enable them, and do not do so on a public deployment."
            ),
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
def analyze(request: AnalyzeRequest, http_request: Request) -> AnalyzeResponse:
    """Fetch data, compute analytics and return the full portfolio picture."""
    allowed, retry_after = limiter.check(client_key(http_request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many analysis requests. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        return service.analyze(request, persist=settings.persist_portfolios)
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
    require_warehouse_api()
    if request.command not in {"build", "run", "test", "seed", "compile"}:
        raise HTTPException(status_code=400, detail=f"Unsupported dbt command: {request.command}")
    return warehouse.run_dbt(request.command, request.select)


@app.get("/api/warehouse/tables")
def tables() -> list[dict]:
    require_warehouse_api()
    return warehouse.list_tables()


class QueryRequest(BaseModel):
    sql: str
    limit: int = 500


@app.post("/api/warehouse/query")
def run_query(request: QueryRequest) -> dict:
    """Read-only SQL against the warehouse, for exploring the dbt marts."""
    require_warehouse_api()
    try:
        rows = warehouse.query(request.sql, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}") from exc
    return {"rows": rows, "count": len(rows)}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
#
# Serving the built SPA from the API turns a deployment into one container on
# one origin, which removes the CORS surface entirely and halves the number of
# things to operate. This block is a no-op when `web/dist` has not been built,
# so local development still runs the Vite dev server against a bare API.
#
# Registered last on purpose: the catch-all below must not shadow /api routes.

_static_dir = settings.static_dir

if _static_dir.is_dir():
    # Hashed asset filenames are safe to cache indefinitely.
    app.mount(
        "/assets",
        StaticFiles(directory=_static_dir / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        """Serve the SPA, falling back to index.html for client-side routes.

        An unknown /api/* path must still 404 as an API error rather than
        silently returning the HTML shell, which would turn a typo in a fetch
        URL into a confusing JSON parse error in the browser.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Serve a real file when one matches, resolving through the directory
        # to reject any path that escapes it.
        if full_path:
            candidate = (_static_dir / full_path).resolve()
            try:
                candidate.relative_to(_static_dir.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found") from None
            if candidate.is_file():
                return FileResponse(candidate)

        index = _static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend is not built")
        return FileResponse(index)

    log.info("Serving frontend from %s", _static_dir)
else:
    log.info(
        "No built frontend at %s; API only. Run 'npm run build' in web/ to serve it.",
        _static_dir,
    )
