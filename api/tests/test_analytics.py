"""Unit tests for the analytics primitives.

These use hand-built return series so each assertion checks a property we can
reason about independently of any market data source.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app import analytics
from app.schemas import SecurityMeta


def make_prices(n: int = 500, seed: int = 0, tickers=("A", "B", "C")) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2022-01-03", periods=n)
    data = {t: 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n))) for t in tickers}
    return pd.DataFrame(data, index=index)


class TestReturns:
    def test_daily_returns_shape(self):
        prices = make_prices(100)
        returns = analytics.daily_returns(prices)
        # One row is consumed computing the first difference.
        assert len(returns) == 99
        assert list(returns.columns) == ["A", "B", "C"]

    def test_constant_prices_give_zero_returns(self):
        index = pd.bdate_range("2024-01-01", periods=10)
        prices = pd.DataFrame({"A": [50.0] * 10}, index=index)
        assert analytics.daily_returns(prices)["A"].abs().max() == 0.0

    def test_portfolio_return_is_weighted_average(self):
        index = pd.bdate_range("2024-01-01", periods=3)
        returns = pd.DataFrame({"A": [0.10, 0.0, -0.10], "B": [0.0, 0.20, 0.0]}, index=index)
        port = analytics.portfolio_returns(returns, {"A": 0.5, "B": 0.5})
        assert port.tolist() == pytest.approx([0.05, 0.10, -0.05])

    def test_weights_are_renormalized(self):
        """Weights that do not sum to 1 are rescaled rather than rejected."""
        index = pd.bdate_range("2024-01-01", periods=2)
        returns = pd.DataFrame({"A": [0.10, 0.10], "B": [0.0, 0.0]}, index=index)
        port = analytics.portfolio_returns(returns, {"A": 2.0, "B": 2.0})
        assert port.tolist() == pytest.approx([0.05, 0.05])

    def test_growth_curve_compounds(self):
        index = pd.bdate_range("2024-01-01", periods=2)
        returns = pd.Series([0.10, 0.10], index=index)
        assert analytics.growth_curve(returns, 100).tolist() == pytest.approx([110.0, 121.0])

    def test_drawdown_is_zero_at_new_highs(self):
        index = pd.bdate_range("2024-01-01", periods=4)
        returns = pd.Series([0.05, 0.05, 0.05, 0.05], index=index)
        assert analytics.drawdown_series(returns).abs().max() == pytest.approx(0.0)

    def test_drawdown_measures_peak_to_trough(self):
        index = pd.bdate_range("2024-01-01", periods=3)
        # +100% then -50% returns exactly to the starting value: a 50% drawdown.
        returns = pd.Series([1.0, -0.5, 0.0], index=index)
        assert analytics.drawdown_series(returns).min() == pytest.approx(-0.5)


class TestRiskMetrics:
    def test_empty_series_returns_empty_metrics(self):
        assert analytics.risk_metrics(pd.Series(dtype=float)).annual_vol is None

    def test_volatility_annualizes_by_sqrt_time(self):
        rng = np.random.default_rng(42)
        daily_vol = 0.01
        index = pd.bdate_range("2020-01-01", periods=2000)
        returns = pd.Series(rng.normal(0, daily_vol, 2000), index=index)
        metrics = analytics.risk_metrics(returns)
        expected = daily_vol * math.sqrt(252)
        assert metrics.annual_vol == pytest.approx(expected, rel=0.06)

    def test_beta_of_series_against_itself_is_one(self):
        rng = np.random.default_rng(7)
        index = pd.bdate_range("2022-01-03", periods=400)
        series = pd.Series(rng.normal(0.0005, 0.011, 400), index=index)
        assert analytics.risk_metrics(series, series).beta == pytest.approx(1.0)

    def test_double_leverage_doubles_beta(self):
        rng = np.random.default_rng(11)
        index = pd.bdate_range("2022-01-03", periods=400)
        bench = pd.Series(rng.normal(0.0004, 0.01, 400), index=index)
        assert analytics.risk_metrics(bench * 2, bench).beta == pytest.approx(2.0)

    def test_var_is_a_left_tail_quantile(self):
        rng = np.random.default_rng(3)
        index = pd.bdate_range("2022-01-03", periods=1000)
        returns = pd.Series(rng.normal(0, 0.01, 1000), index=index)
        metrics = analytics.risk_metrics(returns)
        assert metrics.var_95 < 0
        # Conditional VaR is the mean beyond VaR, so it is always at least as bad.
        assert metrics.cvar_95 <= metrics.var_95

    def test_positive_days_fraction(self):
        index = pd.bdate_range("2024-01-01", periods=4)
        returns = pd.Series([0.01, -0.01, 0.01, 0.01], index=index)
        assert analytics.risk_metrics(returns).positive_days == pytest.approx(0.75)


class TestConcentration:
    def test_herfindahl_of_single_position(self):
        assert analytics.herfindahl([1.0]) == pytest.approx(1.0)

    def test_herfindahl_of_equal_weights_is_one_over_n(self):
        assert analytics.herfindahl([0.25] * 4) == pytest.approx(0.25)

    def test_herfindahl_normalizes_unscaled_weights(self):
        assert analytics.herfindahl([10, 10, 10, 10]) == pytest.approx(0.25)

    def test_empty_weights_do_not_divide_by_zero(self):
        assert analytics.herfindahl([]) == 0.0


class TestDiversification:
    def test_risk_contributions_sum_to_one(self):
        returns = analytics.daily_returns(make_prices(400, seed=5))
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        shares, marginals = analytics.risk_contributions(returns, weights)
        assert sum(shares.values()) == pytest.approx(1.0)
        assert set(marginals) == {"A", "B", "C"}

    def test_identical_assets_have_diversification_ratio_of_one(self):
        """Two copies of the same asset combine into no risk reduction at all."""
        index = pd.bdate_range("2022-01-03", periods=300)
        rng = np.random.default_rng(9)
        series = rng.normal(0.0004, 0.01, 300)
        returns = pd.DataFrame({"A": series, "B": series}, index=index)
        weights = {"A": 0.5, "B": 0.5}
        port = analytics.portfolio_returns(returns, weights)
        vol = analytics.risk_metrics(port).annual_vol
        assert analytics.diversification_ratio(returns, weights, vol) == pytest.approx(1.0)

    def test_uncorrelated_assets_beat_a_ratio_of_one(self):
        index = pd.bdate_range("2022-01-03", periods=1500)
        rng = np.random.default_rng(13)
        returns = pd.DataFrame(
            {"A": rng.normal(0, 0.01, 1500), "B": rng.normal(0, 0.01, 1500)}, index=index
        )
        weights = {"A": 0.5, "B": 0.5}
        port = analytics.portfolio_returns(returns, weights)
        vol = analytics.risk_metrics(port).annual_vol
        # Two independent equal-weight assets give a ratio near sqrt(2).
        assert analytics.diversification_ratio(returns, weights, vol) == pytest.approx(
            math.sqrt(2), rel=0.1
        )

    def test_average_correlation_needs_two_positions(self):
        returns = analytics.daily_returns(make_prices(200, tickers=("A",)))
        corr = analytics.correlation_matrix(returns)
        assert analytics.average_correlation(corr, {"A": 1.0}) is None

    def test_score_rises_with_breadth(self):
        """A broad equal-weight book must score above a single concentrated name."""
        broad_prices = make_prices(500, seed=21, tickers=tuple("ABCDEFGHIJ"))
        broad_returns = analytics.daily_returns(broad_prices)
        broad_weights = {t: 0.1 for t in "ABCDEFGHIJ"}
        meta = {
            t: SecurityMeta(ticker=t, sector=f"Sector{i}", asset_class="Equity")
            for i, t in enumerate("ABCDEFGHIJ")
        }
        broad_port = analytics.portfolio_returns(broad_returns, broad_weights)
        broad = analytics.diversification_metrics(
            broad_returns, broad_weights, meta, analytics.risk_metrics(broad_port).annual_vol
        )

        single_returns = broad_returns[["A"]]
        single_weights = {"A": 1.0}
        single_port = analytics.portfolio_returns(single_returns, single_weights)
        single = analytics.diversification_metrics(
            single_returns, single_weights, meta, analytics.risk_metrics(single_port).annual_vol
        )

        assert broad.score > single.score
        assert broad.effective_holdings == pytest.approx(10.0)
        assert single.effective_holdings == pytest.approx(1.0)

    def test_score_is_bounded(self):
        prices = make_prices(400, seed=31, tickers=tuple("ABCDE"))
        returns = analytics.daily_returns(prices)
        weights = {t: 0.2 for t in "ABCDE"}
        meta = {t: SecurityMeta(ticker=t) for t in "ABCDE"}
        port = analytics.portfolio_returns(returns, weights)
        metrics = analytics.diversification_metrics(
            returns, weights, meta, analytics.risk_metrics(port).annual_vol
        )
        assert 0.0 <= metrics.score <= 100.0
        assert metrics.grade in {"A", "B", "C", "D", "F"}


class TestAllocation:
    def test_groups_and_sorts_by_weight(self):
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        meta = {
            "A": SecurityMeta(ticker="A", sector="Tech"),
            "B": SecurityMeta(ticker="B", sector="Tech"),
            "C": SecurityMeta(ticker="C", sector="Energy"),
        }
        slices = analytics.allocation_by(weights, meta, "sector")
        assert [s.label for s in slices] == ["Tech", "Energy"]
        assert slices[0].weight == pytest.approx(0.8)
        assert slices[0].tickers == ["A", "B"]

    def test_missing_metadata_falls_into_unknown(self):
        slices = analytics.allocation_by({"Z": 1.0}, {}, "sector")
        assert slices[0].label == "Unknown"

    def test_allocation_weights_sum_to_one(self):
        weights = {"A": 0.5, "B": 0.3, "C": 0.2}
        meta = {t: SecurityMeta(ticker=t, sector="S", asset_class="Equity") for t in weights}
        for group in analytics.build_allocation(weights, meta).values():
            assert sum(s.weight for s in group) == pytest.approx(1.0)
