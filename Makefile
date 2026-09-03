# Portfolio analysis stack: FastAPI + DuckDB + dbt + React.
#
# Quick start:  make setup && make dev

VENV      := .venv
PY        := $(VENV)/bin/python
PIP       := $(VENV)/bin/pip
DUCKDB    := $(CURDIR)/data/warehouse.duckdb
DBT_DIR   := dbt/portfolio
DBT_FLAGS := --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

export DUCKDB_PATH := $(DUCKDB)

.PHONY: help setup setup-api setup-web api web dev test test-api test-web \
        lint dbt dbt-test dbt-docs seed warehouse clean reset

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: setup-api setup-web ## Install all Python and Node dependencies

setup-api: ## Create the virtualenv and install the API with dbt support
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e 'api[dev,dbt]'
	@echo
	@echo "Installed with the offline demo provider."
	@echo "For real market data:  $(PIP) install -e 'api[yfinance]'"
	@echo "Or, preferably:        $(PIP) install -e 'api[openbb]'"

setup-web: ## Install frontend dependencies
	cd web && npm install

api: ## Run the API on :8000 with reload
	cd api && ../$(VENV)/bin/uvicorn app.main:app --reload --port 8000

web: ## Run the frontend dev server on :5173
	cd web && npm run dev

dev: ## Run API and frontend together
	@echo "API   -> http://127.0.0.1:8000/docs"
	@echo "Web   -> http://127.0.0.1:5173"
	@$(MAKE) -j2 api web

test: test-api test-web ## Run all tests

test-api: ## Run the Python test suite
	cd api && ../$(VENV)/bin/python -m pytest tests -q

test-web: ## Run the frontend test suite
	cd web && npm test

lint: ## Typecheck the frontend and lint the API
	cd web && npm run typecheck
	$(VENV)/bin/ruff check api || true

seed: ## Populate the warehouse with a few example portfolios
	cd api && ../$(VENV)/bin/python -m app.seed

dbt: ## Build the dbt models
	$(VENV)/bin/dbt build $(DBT_FLAGS)

dbt-test: ## Run dbt tests only
	$(VENV)/bin/dbt test $(DBT_FLAGS)

dbt-docs: ## Generate and serve the dbt documentation site
	$(VENV)/bin/dbt docs generate $(DBT_FLAGS)
	$(VENV)/bin/dbt docs serve $(DBT_FLAGS)

warehouse: seed dbt ## Seed example data and build every model

clean: ## Remove build artifacts and caches
	rm -rf web/dist web/node_modules/.vite
	rm -rf $(DBT_DIR)/target $(DBT_DIR)/logs
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name .pytest_cache -type d -prune -exec rm -rf {} +

reset: clean ## Also delete the DuckDB warehouse
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal
