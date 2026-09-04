"""Point every test at a throwaway warehouse.

Without this the suite writes portfolio snapshots into the developer's real
DuckDB file, so `dbt build` would be analyzing test fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_warehouse():
    with tempfile.TemporaryDirectory() as tmp:
        from app.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.duckdb_path = Path(tmp) / "test_warehouse.duckdb"
        yield settings.duckdb_path
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_rate_limit():
    """Disable throttling for every test that does not explicitly want it.

    The suite makes far more analysis calls than a real client would, and a
    test failing because a previous test used up the allowance would be a
    confusing false negative. Rate limiting has its own dedicated tests.
    """
    from app import main

    original = main.limiter.limit
    main.limiter.limit = 0
    main.limiter.reset()
    yield
    main.limiter.limit = original
    main.limiter.reset()
