"""Endpoint and pipeline tests, driven entirely through the offline demo provider."""

from __future__ import annotations

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AnalyzeRequest

client = TestClient(app)


def payload(holdings, **kwargs):
    body = {
        "holdings": [{"ticker": t, "weight": w} for t, w in holdings],
        "provider": "demo",
        "lookback_days": 730,
    }
    body.update(kwargs)
    return body


class TestHealth:
    def test_health_reports_providers(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        # The demo provider has no dependencies, so it is always available.
        assert body["providers"]["demo"] is True


class TestSearch:
    def test_exact_ticker_ranks_first(self):
        results = client.get("/api/search", params={"q": "AAPL"}).json()
        assert results[0]["ticker"] == "AAPL"

    def test_name_substring_matches(self):
        tickers = [r["ticker"] for r in client.get("/api/search", params={"q": "vanguard"}).json()]
        assert "VTI" in tickers

    def test_unknown_query_returns_empty(self):
        assert client.get("/api/search", params={"q": "ZZZQQQ"}).json() == []

    def test_blank_query_is_rejected(self):
        assert client.get("/api/search", params={"q": ""}).status_code == 422


class TestAnalyze:
    def test_returns_a_complete_analysis(self):
        response = client.post(
            "/api/portfolio/analyze",
            json=payload([("AAPL", 40), ("MSFT", 30), ("BND", 30)]),
        )
        assert response.status_code == 200
        body = response.json()

        assert body["data_quality"]["provider"] == "demo"
        assert len(body["holdings"]) == 3
        assert body["performance"]
        assert body["correlation"]["tickers"] == ["AAPL", "MSFT", "BND"]
        assert 0 <= body["diversification"]["score"] <= 100

    def test_percentage_weights_are_normalized(self):
        body = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 60), ("BND", 40)])
        ).json()
        assert sum(h["weight"] for h in body["holdings"]) == pytest.approx(1.0)

    def test_decimal_weights_give_the_same_answer(self):
        """Entering 0.6/0.4 must be identical to entering 60/40."""
        pct = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 60), ("BND", 40)])
        ).json()
        dec = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 0.6), ("BND", 0.4)])
        ).json()
        assert pct["diversification"]["score"] == dec["diversification"]["score"]

    def test_unweighted_ratios_are_normalized(self):
        body = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 1), ("MSFT", 1), ("BND", 2)])
        ).json()
        weights = {h["ticker"]: h["weight"] for h in body["holdings"]}
        assert weights["BND"] == pytest.approx(0.5)

    def test_risk_contributions_sum_to_one(self):
        body = client.post(
            "/api/portfolio/analyze",
            json=payload([("AAPL", 25), ("NVDA", 25), ("BND", 25), ("GLD", 25)]),
        ).json()
        total = sum(h["contribution_to_risk"] for h in body["holdings"])
        assert total == pytest.approx(1.0)

    def test_allocation_groups_are_present(self):
        body = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 50), ("BND", 50)])
        ).json()
        allocation = body["allocation"]
        for key in ("by_ticker", "by_sector", "by_asset_class", "by_country"):
            assert key in allocation
            assert sum(s["weight"] for s in allocation[key]) == pytest.approx(1.0)

    def test_benchmark_series_is_returned(self):
        body = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 100)], benchmark="SPY")
        ).json()
        assert body["benchmark"] == "SPY"
        assert body["performance"][-1]["benchmark"] is not None
        assert body["benchmark_risk"]["annual_vol"] is not None

    def test_holdings_are_ordered_by_weight(self):
        body = client.post(
            "/api/portfolio/analyze",
            json=payload([("BND", 10), ("AAPL", 60), ("MSFT", 30)]),
        ).json()
        weights = [h["weight"] for h in body["holdings"]]
        assert weights == sorted(weights, reverse=True)


class TestValidation:
    def test_duplicate_tickers_are_rejected(self):
        response = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 50), ("AAPL", 50)])
        )
        assert response.status_code == 422

    def test_empty_holdings_are_rejected(self):
        assert client.post("/api/portfolio/analyze", json=payload([])).status_code == 422

    def test_zero_total_weight_is_rejected(self):
        response = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 0), ("MSFT", 0)])
        )
        assert response.status_code == 422

    def test_negative_weight_is_rejected(self):
        response = client.post("/api/portfolio/analyze", json=payload([("AAPL", -10)]))
        assert response.status_code == 422

    def test_tickers_are_upper_cased_and_trimmed(self):
        request = AnalyzeRequest(holdings=[{"ticker": "  aapl ", "weight": 1}])
        assert request.holdings[0].ticker == "AAPL"

    def test_accepts_dollar_amounts_as_weights(self):
        """The UI can submit money invested per position, not just percentages."""
        response = client.post(
            "/api/portfolio/analyze",
            json=payload([("VTI", 5000), ("VXUS", 3000), ("BND", 2000)]),
        )
        assert response.status_code == 200
        weights = {h["ticker"]: h["weight"] for h in response.json()["holdings"]}
        assert weights["VTI"] == pytest.approx(0.5)
        assert weights["VXUS"] == pytest.approx(0.3)
        assert weights["BND"] == pytest.approx(0.2)

    def test_dollar_amounts_match_the_equivalent_percentages(self):
        """$5k/$3k/$2k must analyze identically to 50/30/20."""
        dollars = client.post(
            "/api/portfolio/analyze",
            json=payload([("VTI", 5000), ("VXUS", 3000), ("BND", 2000)]),
        ).json()
        percents = client.post(
            "/api/portfolio/analyze",
            json=payload([("VTI", 50), ("VXUS", 30), ("BND", 20)]),
        ).json()
        assert dollars["diversification"] == percents["diversification"]
        assert dollars["risk"] == percents["risk"]

    def test_rejects_an_implausibly_large_weight(self):
        response = client.post("/api/portfolio/analyze", json=payload([("VTI", 1e13)]))
        assert response.status_code == 422

    def test_lookback_window_is_bounded(self):
        response = client.post(
            "/api/portfolio/analyze", json=payload([("AAPL", 100)], lookback_days=5)
        )
        assert response.status_code == 422


class TestOpportunities:
    def _opportunities(self, holdings, **kwargs):
        body = client.post(
            "/api/portfolio/analyze", json=payload(holdings, **kwargs)
        ).json()
        return {o["id"]: o for o in body["opportunities"]}

    def test_flags_a_dominant_single_position(self):
        found = self._opportunities([("AAPL", 70), ("MSFT", 15), ("BND", 15)])
        assert "concentration-single" in found
        assert found["concentration-single"]["severity"] == "critical"
        assert found["concentration-single"]["tickers"] == ["AAPL"]

    def test_flags_sector_concentration(self):
        found = self._opportunities(
            [("AAPL", 25), ("MSFT", 25), ("NVDA", 25), ("AVGO", 25)]
        )
        assert any(o["kind"] == "sector" for o in found.values())

    def test_flags_missing_defensive_ballast(self):
        found = self._opportunities([("AAPL", 34), ("MSFT", 33), ("GOOGL", 33)])
        assert "no-ballast" in found

    def test_no_ballast_flag_clears_when_bonds_are_held(self):
        found = self._opportunities(
            [("VTI", 30), ("VXUS", 25), ("BND", 25), ("GLD", 20)]
        )
        assert "no-ballast" not in found

    def test_flags_home_bias(self):
        found = self._opportunities([("AAPL", 34), ("MSFT", 33), ("JPM", 33)])
        assert "home-bias" in found

    def test_home_bias_clears_with_international_exposure(self):
        found = self._opportunities(
            [("VTI", 40), ("VXUS", 30), ("VWO", 15), ("BND", 15)]
        )
        assert "home-bias" not in found

    def test_flags_low_effective_breadth(self):
        found = self._opportunities([("AAPL", 45), ("MSFT", 45), ("BND", 10)])
        assert "breadth-low" in found

    def test_opportunities_are_sorted_by_severity(self):
        body = client.post(
            "/api/portfolio/analyze",
            json=payload([("NVDA", 60), ("AAPL", 20), ("MSFT", 20)]),
        ).json()
        rank = {"critical": 0, "warning": 1, "info": 2}
        severities = [rank[o["severity"]] for o in body["opportunities"]]
        assert severities == sorted(severities)

    def test_every_opportunity_is_self_describing(self):
        body = client.post(
            "/api/portfolio/analyze", json=payload([("NVDA", 80), ("AAPL", 20)])
        ).json()
        for opportunity in body["opportunities"]:
            assert opportunity["title"]
            assert opportunity["detail"]
            assert opportunity["kind"]


@pytest.fixture
def warehouse_api_enabled():
    """Temporarily enable the operator-only warehouse endpoints."""
    from app import main

    original = main.settings.enable_warehouse_api
    main.settings.enable_warehouse_api = True
    yield
    main.settings.enable_warehouse_api = original


class TestWarehouseEndpointsAreGated:
    """These run arbitrary SQL and invoke dbt, so they must be opt-in."""

    def test_tables_is_disabled_by_default(self):
        assert client.get("/api/warehouse/tables").status_code == 404

    def test_query_is_disabled_by_default(self):
        response = client.post("/api/warehouse/query", json={"sql": "select 1"})
        assert response.status_code == 404

    def test_dbt_is_disabled_by_default(self):
        response = client.post("/api/warehouse/dbt", json={"command": "build"})
        assert response.status_code == 404

    def test_the_refusal_explains_how_to_enable(self):
        detail = client.get("/api/warehouse/tables").json()["detail"]
        assert "PORTFOLIO_ENABLE_WAREHOUSE_API" in detail


class TestWarehouseEndpoints:
    def test_lists_tables(self, warehouse_api_enabled):
        response = client.get("/api/warehouse/tables")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_rejects_non_select_sql(self, warehouse_api_enabled):
        response = client.post(
            "/api/warehouse/query", json={"sql": "DROP TABLE raw.prices"}
        )
        assert response.status_code == 400

    def test_rejects_unsupported_dbt_command(self, warehouse_api_enabled):
        response = client.post("/api/warehouse/dbt", json={"command": "destroy"})
        assert response.status_code == 400


class TestRateLimiting:
    def test_blocks_once_the_allowance_is_spent(self):
        from app import main

        main.limiter.limit = 2
        main.limiter.reset()
        try:
            body = payload([("VTI", 100)])
            assert client.post("/api/portfolio/analyze", json=body).status_code == 200
            assert client.post("/api/portfolio/analyze", json=body).status_code == 200

            blocked = client.post("/api/portfolio/analyze", json=body)
            assert blocked.status_code == 429
            assert "Retry-After" in blocked.headers
        finally:
            main.limiter.limit = 0
            main.limiter.reset()

    def test_search_is_not_throttled(self):
        """Autocomplete fires on every keystroke; throttling it would break typing."""
        from app import main

        main.limiter.limit = 1
        main.limiter.reset()
        try:
            for _ in range(10):
                assert client.get("/api/search", params={"q": "V"}).status_code == 200
        finally:
            main.limiter.limit = 0
            main.limiter.reset()


class TestPersistenceSwitch:
    """A public deployment must not accumulate snapshots from anonymous users."""

    @staticmethod
    def _holdings_rows() -> int:
        from app import warehouse

        warehouse.initialize()
        con = warehouse.connect(read_only=True)
        try:
            return con.execute(
                f"SELECT COUNT(*) FROM {warehouse.RAW_SCHEMA}.portfolio_holdings"
            ).fetchone()[0]
        finally:
            con.close()

    def test_disabled_persistence_writes_no_snapshot(self):
        from app import main

        original = main.settings.persist_portfolios
        main.settings.persist_portfolios = False
        try:
            before = self._holdings_rows()
            response = client.post(
                "/api/portfolio/analyze", json=payload([("VTI", 60), ("BND", 40)])
            )
            assert response.status_code == 200
            assert self._holdings_rows() == before
        finally:
            main.settings.persist_portfolios = original

    def test_enabled_persistence_writes_a_snapshot(self):
        from app import main

        original = main.settings.persist_portfolios
        main.settings.persist_portfolios = True
        try:
            before = self._holdings_rows()
            response = client.post(
                "/api/portfolio/analyze", json=payload([("VTI", 60), ("BND", 40)])
            )
            assert response.status_code == 200
            assert self._holdings_rows() > before
        finally:
            main.settings.persist_portfolios = original


class TestWarehouseIsOptional:
    def test_an_unwritable_warehouse_path_does_not_break_startup(self):
        """The warehouse is a cache. A bad path must not take the site down."""
        import importlib

        from app import config

        config.get_settings.cache_clear()
        try:
            with mock.patch.dict(
                os.environ, {"PORTFOLIO_DUCKDB_PATH": "/proc/nope/warehouse.duckdb"}
            ):
                settings = config.get_settings()
                assert settings.duckdb_path.name == "warehouse.duckdb"
                # Importing the app must still succeed.
                importlib.reload(importlib.import_module("app.main"))
        finally:
            config.get_settings.cache_clear()
            importlib.reload(importlib.import_module("app.main"))


class TestFrontendServing:
    def test_unknown_api_path_stays_a_json_404(self):
        """It must not fall through to the SPA shell and confuse a fetch call."""
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")
