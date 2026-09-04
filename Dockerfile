# Single-image deployment: the API serves both the JSON endpoints and the built
# React app, so a running site is one container on one origin. That removes the
# CORS surface entirely and leaves one thing to deploy, scale and monitor.

# --- Stage 1: build the frontend ------------------------------------------
FROM node:22-alpine AS web

WORKDIR /build

# Copy manifests first so this layer is cached until dependencies change.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


# --- Stage 2: runtime ------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORTFOLIO_STATIC_DIR=/app/web/dist \
    PORTFOLIO_DUCKDB_PATH=/data/warehouse.duckdb \
    PORTFOLIO_ENABLE_WAREHOUSE_API=false \
    PORTFOLIO_PERSIST_PORTFOLIOS=false

WORKDIR /app

# Install dependencies before the source so code edits do not reinstall them.
COPY api/pyproject.toml ./api/
COPY api/app/__init__.py ./api/app/
RUN pip install --no-cache-dir -e './api[yfinance]'

COPY api/ ./api/
COPY dbt/ ./dbt/
COPY --from=web /build/dist ./web/dist

# Run unprivileged, and give the warehouse a directory the app owns. Mount a
# volume at /data to keep it across restarts; without one it is ephemeral,
# which is fine since prices are refetched on demand.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Hosts inject $PORT; default to 8000 for plain `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --app-dir /app/api --host 0.0.0.0 --port ${PORT:-8000}"]
