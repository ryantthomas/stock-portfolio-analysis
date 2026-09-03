"""Orchestration: fetch market data, run the analytics, land it in the warehouse."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from app import analytics, warehouse
from app.config import get_settings
from app.providers import ProviderResult, fetch
from app.providers.base import reference_metadata
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DataQuality,
    RiskMetrics,
)

log = logging.getLogger(__name__)


def analyze(request: AnalyzeRequest, persist: bool = True) -> AnalyzeResponse:
    """Run the full analysis pipeline for one portfolio request."""
    settings = get_settings()
    analytics.TRADING_DAYS = settings.trading_days

    requested = [h.ticker for h in request.holdings]
    end = date.today()
    start = end - timedelta(days=request.lookback_days)

    # The benchmark is fetched alongside the holdings so both series share a
    # calendar; comparing them across mismatched date ranges is meaningless.
    symbols = list(dict.fromkeys([*requested, request.benchmark]))
    result: ProviderResult = fetch(symbols, start, end, request.provider)

    prices = result.prices
    resolved = [t for t in requested if t in prices.columns]
    missing = [t for t in requested if t not in prices.columns]
    if not resolved:
        raise ValueError(
            f"No price history for any requested ticker: {', '.join(requested)}"
        )

    # Rescale so the tickers that did resolve still sum to 100%.
    raw_weights = request.normalized_weights()
    kept = {t: raw_weights[t] for t in resolved}
    total = sum(kept.values())
    weights = {t: w / total for t, w in kept.items()} if total > 0 else kept

    metadata = dict(result.metadata)
    for ticker in symbols:
        if ticker not in metadata:
            metadata[ticker] = reference_metadata(ticker)

    returns = analytics.daily_returns(prices)
    holdings_returns = returns[[c for c in resolved if c in returns.columns]]

    port_returns = analytics.portfolio_returns(returns, weights)
    bench_returns = (
        returns[request.benchmark]
        if request.benchmark in returns.columns
        else pd.Series(dtype=float)
    )

    risk = analytics.risk_metrics(port_returns, bench_returns, settings.risk_free_rate)
    bench_risk = (
        analytics.risk_metrics(bench_returns, None, settings.risk_free_rate)
        if not bench_returns.empty
        else RiskMetrics()
    )

    div = analytics.diversification_metrics(
        holdings_returns, weights, metadata, risk.annual_vol
    )
    opportunities = analytics.detect_opportunities(
        weights, metadata, holdings_returns, div, risk, bench_risk, request.benchmark
    )

    performance, drawdown = analytics.build_series(port_returns, bench_returns)
    holdings = analytics.build_holdings(weights, metadata, prices, holdings_returns)
    correlation = analytics.build_correlation(holdings_returns, resolved)
    allocation = analytics.build_allocation(weights, metadata)

    warnings = list(result.warnings)
    if missing:
        warnings.append(
            f"Dropped and reweighted around {', '.join(missing)} -- no price history."
        )
    if request.benchmark not in prices.columns:
        warnings.append(
            f"Benchmark {request.benchmark} unavailable; comparison metrics omitted."
        )

    index_dates = [d.date() if hasattr(d, "date") else d for d in prices.index]

    if persist:
        _persist(result, weights, request.benchmark, request.label)

    return AnalyzeResponse(
        as_of=index_dates[-1] if index_dates else None,
        benchmark=request.benchmark,
        data_quality=DataQuality(
            provider=result.provider,
            requested=requested,
            resolved=resolved,
            missing=missing,
            warnings=warnings,
            history_start=index_dates[0] if index_dates else None,
            history_end=index_dates[-1] if index_dates else None,
            observations=len(returns),
        ),
        holdings=holdings,
        allocation=allocation,
        performance=performance,
        drawdown=drawdown,
        risk=risk,
        benchmark_risk=bench_risk,
        diversification=div,
        correlation=correlation,
        opportunities=opportunities,
    )


def _persist(
    result: ProviderResult,
    weights: dict[str, float],
    benchmark: str,
    label: str | None = None,
) -> None:
    """Land raw data in DuckDB. Never fail the request over a warehouse error."""
    try:
        warehouse.load_prices(result.prices, result.provider)
        warehouse.load_securities(result.metadata, result.provider)
        warehouse.save_portfolio(weights, benchmark, label)
    except Exception as exc:  # noqa: BLE001 - persistence is a side effect
        log.warning("Warehouse persistence failed: %s", exc)
