"""Portfolio analytics: performance, risk, diversification and opportunities.

Everything here operates on a price panel (dates x tickers) and a weight
vector. The functions are pure and provider-agnostic, which keeps them
straightforward to unit test against synthetic data.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from app.reference import BENCHMARK_SECTOR_WEIGHTS, DEFENSIVE_ASSET_CLASSES
from app.schemas import (
    AllocationSlice,
    CorrelationMatrix,
    DiversificationMetrics,
    DrawdownPoint,
    HoldingDetail,
    Opportunity,
    RiskMetrics,
    SecurityMeta,
    SeriesPoint,
)

TRADING_DAYS = 252


# --------------------------------------------------------------------------
# Return series
# --------------------------------------------------------------------------


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns, with leading/trailing all-NaN rows dropped.

    Forward-filling first means a ticker that does not trade on a given day
    (a holiday in its home market, say) contributes a 0% return rather than
    knocking the whole row out of the panel.
    """
    clean = prices.sort_index().ffill().dropna(how="all")
    returns = clean.pct_change().dropna(how="all")
    return returns.fillna(0.0)


def portfolio_returns(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted daily return of a portfolio rebalanced back to target each day.

    Daily rebalancing keeps weights equal to the user's stated targets, which
    is what makes the reported statistics describe the allocation they entered
    rather than whatever it happened to drift into.
    """
    cols = [c for c in returns.columns if c in weights]
    if not cols:
        return pd.Series(dtype=float)
    w = np.array([weights[c] for c in cols], dtype=float)
    total = w.sum()
    if total <= 0:
        return pd.Series(dtype=float)
    w = w / total
    return pd.Series(returns[cols].to_numpy() @ w, index=returns.index, name="portfolio")


def growth_curve(returns: pd.Series, base: float = 100.0) -> pd.Series:
    """Cumulative growth of `base` invested at the start of the window."""
    if returns.empty:
        return pd.Series(dtype=float)
    return base * (1.0 + returns).cumprod()


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Percentage below the running high-water mark, as a negative decimal."""
    if returns.empty:
        return pd.Series(dtype=float)
    curve = growth_curve(returns)
    return curve / curve.cummax() - 1.0


# --------------------------------------------------------------------------
# Risk metrics
# --------------------------------------------------------------------------


def _annualized_return(returns: pd.Series) -> float | None:
    """Compound annual growth rate over the observed window."""
    if returns.empty:
        return None
    total = float((1.0 + returns).prod())
    years = len(returns) / TRADING_DAYS
    if years <= 0 or total <= 0:
        return None
    return total ** (1.0 / years) - 1.0


def risk_metrics(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    risk_free_rate: float = 0.042,
) -> RiskMetrics:
    """Standard risk statistics for a daily return series."""
    if returns.empty:
        return RiskMetrics()

    ann_return = _annualized_return(returns)
    ann_vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(returns) > 1 else None

    sharpe = None
    if ann_return is not None and ann_vol:
        sharpe = (ann_return - risk_free_rate) / ann_vol

    # Sortino penalizes only downside deviation, measured against the daily
    # risk-free rate rather than zero.
    sortino = None
    daily_rf = risk_free_rate / TRADING_DAYS
    downside = returns[returns < daily_rf] - daily_rf
    if len(downside) > 1:
        dd = float(downside.std(ddof=1) * math.sqrt(TRADING_DAYS))
        if dd > 0 and ann_return is not None:
            sortino = (ann_return - risk_free_rate) / dd

    dd_series = drawdown_series(returns)
    max_dd = float(dd_series.min()) if not dd_series.empty else None

    # Historical (non-parametric) VaR and the expected loss beyond it.
    var_95 = float(np.percentile(returns, 5)) if len(returns) >= 20 else None
    tail = returns[returns <= var_95] if var_95 is not None else pd.Series(dtype=float)
    cvar_95 = float(tail.mean()) if len(tail) > 0 else None

    beta = alpha = tracking_error = None
    if benchmark is not None and not benchmark.empty:
        aligned = pd.concat([returns, benchmark], axis=1, join="inner").dropna()
        if len(aligned) > 2:
            r = aligned.iloc[:, 0].to_numpy()
            b = aligned.iloc[:, 1].to_numpy()
            bench_var = float(np.var(b, ddof=1))
            if bench_var > 0:
                beta = float(np.cov(r, b, ddof=1)[0, 1] / bench_var)
                bench_ann = _annualized_return(pd.Series(b))
                if ann_return is not None and bench_ann is not None:
                    # Jensen's alpha.
                    alpha = ann_return - (
                        risk_free_rate + beta * (bench_ann - risk_free_rate)
                    )
            active = r - b
            if len(active) > 1:
                tracking_error = float(np.std(active, ddof=1) * math.sqrt(TRADING_DAYS))

    return RiskMetrics(
        annual_return=ann_return,
        annual_vol=ann_vol,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        beta=beta,
        alpha=alpha,
        tracking_error=tracking_error,
        var_95=var_95,
        cvar_95=cvar_95,
        best_day=float(returns.max()),
        worst_day=float(returns.min()),
        positive_days=float((returns > 0).mean()),
    )


# --------------------------------------------------------------------------
# Concentration and diversification
# --------------------------------------------------------------------------


def herfindahl(weights: list[float]) -> float:
    """Sum of squared weights. 1.0 is a single position; 1/n is equal weight."""
    total = sum(weights)
    if total <= 0:
        return 0.0
    return float(sum((w / total) ** 2 for w in weights))


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pairwise correlation of daily returns, ignoring zero-variance columns."""
    usable = returns.loc[:, returns.std(ddof=1) > 0]
    if usable.shape[1] < 2:
        return pd.DataFrame(index=returns.columns, columns=returns.columns, dtype=float)
    return usable.corr()


def average_correlation(corr: pd.DataFrame, weights: dict[str, float]) -> float | None:
    """Weight-aware mean of the off-diagonal correlations.

    Weighting by the product of position sizes means a pair of tiny holdings
    that happen to move together does not dominate the headline number.
    """
    cols = [c for c in corr.columns if c in weights]
    if len(cols) < 2:
        return None

    num = 0.0
    den = 0.0
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            rho = corr.loc[a, b]
            if pd.isna(rho):
                continue
            pair_weight = weights[a] * weights[b]
            num += pair_weight * float(rho)
            den += pair_weight
    return num / den if den > 0 else None


def diversification_ratio(
    returns: pd.DataFrame, weights: dict[str, float], portfolio_vol: float | None
) -> float | None:
    """Weighted-average asset volatility divided by realized portfolio volatility.

    1.0 means the positions all move as one and combining them bought nothing.
    Higher values mean volatility actually cancelled out.
    """
    if not portfolio_vol or portfolio_vol <= 0:
        return None
    cols = [c for c in returns.columns if c in weights]
    if not cols:
        return None
    vols = returns[cols].std(ddof=1) * math.sqrt(TRADING_DAYS)
    weighted_vol = float(sum(weights[c] * float(vols[c]) for c in cols))
    return weighted_vol / portfolio_vol if weighted_vol > 0 else None


def risk_contributions(
    returns: pd.DataFrame, weights: dict[str, float]
) -> tuple[dict[str, float], dict[str, float]]:
    """Split total portfolio risk across positions.

    Returns ``(contribution_share, marginal_risk)`` where the shares sum to 1.
    A position's risk contribution is its weight times its marginal
    contribution -- the derivative of portfolio volatility with respect to that
    weight. This is where a 5% position in something volatile and correlated
    shows up as 15% of the risk.
    """
    cols = [c for c in returns.columns if c in weights]
    if len(cols) < 1:
        return {}, {}

    w = np.array([weights[c] for c in cols], dtype=float)
    if w.sum() <= 0:
        return {}, {}
    w = w / w.sum()

    cov = returns[cols].cov(ddof=1).to_numpy() * TRADING_DAYS
    port_var = float(w @ cov @ w)
    if port_var <= 0:
        return {}, {}
    port_vol = math.sqrt(port_var)

    marginal = (cov @ w) / port_vol
    contrib = w * marginal
    total = contrib.sum()
    if total <= 0:
        return {}, {}

    shares = {c: float(contrib[i] / total) for i, c in enumerate(cols)}
    marginals = {c: float(marginal[i]) for i, c in enumerate(cols)}
    return shares, marginals


def _grade(score: float) -> str:
    for threshold, label in ((85, "A"), (70, "B"), (55, "C"), (40, "D")):
        if score >= threshold:
            return label
    return "F"


def diversification_metrics(
    returns: pd.DataFrame,
    weights: dict[str, float],
    metadata: dict[str, SecurityMeta],
    portfolio_vol: float | None,
) -> DiversificationMetrics:
    """Composite 0-100 diversification score plus the parts it is built from.

    The score is deliberately explainable: each component is reported alongside
    the total so a user can see *why* a portfolio scored the way it did rather
    than being handed an opaque number.
    """
    tickers = list(weights)
    w_list = [weights[t] for t in tickers]
    ordered = sorted(w_list, reverse=True)

    hhi = herfindahl(w_list)
    effective = 1.0 / hhi if hhi > 0 else 0.0
    top_weight = ordered[0] if ordered else 0.0
    top5 = float(sum(ordered[:5]))

    corr = correlation_matrix(returns)
    avg_corr = average_correlation(corr, weights) if not corr.empty else None
    div_ratio = diversification_ratio(returns, weights, portfolio_vol)

    sector_weights: dict[str, float] = {}
    class_weights: dict[str, float] = {}
    for ticker, weight in weights.items():
        meta = metadata.get(ticker)
        sector = meta.sector if meta else "Unknown"
        asset_class = meta.asset_class if meta else "Unknown"
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
        class_weights[asset_class] = class_weights.get(asset_class, 0.0) + weight

    sector_hhi = herfindahl(list(sector_weights.values())) if sector_weights else None

    # --- Components, each normalized to 0-1 -------------------------------
    # Position breadth saturates at 20 effective holdings; past that, adding
    # names does very little for diversification.
    breadth = min(effective / 20.0, 1.0)
    # Concentration keys off the single largest position rather than the top 5,
    # because any portfolio of five or fewer names has a top-5 weight of 100%
    # and would otherwise score zero here purely for being small -- something
    # the breadth component already measures.
    concentration = max(0.0, min((0.50 - top_weight) / 0.45, 1.0))
    # Correlation is the component that matters most: 20 names that all move
    # together are not diversified, however many of them there are.
    if avg_corr is None:
        correlation_component = 0.5
    else:
        correlation_component = max(0.0, min((0.9 - avg_corr) / 0.9, 1.0))
    # Sector spread.
    if sector_hhi is None:
        sector_component = 0.5
    else:
        sector_component = max(0.0, min((1.0 - sector_hhi) / 0.85, 1.0))
    # Asset-class breadth, credited up to four distinct classes.
    class_component = min(len(class_weights) / 4.0, 1.0)

    components = {
        "position_breadth": round(breadth, 4),
        "concentration": round(concentration, 4),
        "correlation": round(correlation_component, 4),
        "sector_spread": round(sector_component, 4),
        "asset_class_breadth": round(class_component, 4),
    }
    score = 100.0 * (
        0.25 * breadth
        + 0.15 * concentration
        + 0.30 * correlation_component
        + 0.20 * sector_component
        + 0.10 * class_component
    )

    return DiversificationMetrics(
        holdings_count=len(tickers),
        hhi=round(hhi, 6),
        effective_holdings=round(effective, 2),
        top_weight=round(top_weight, 6),
        top5_weight=round(top5, 6),
        avg_correlation=round(avg_corr, 4) if avg_corr is not None else None,
        diversification_ratio=round(div_ratio, 4) if div_ratio is not None else None,
        sector_count=len(sector_weights),
        sector_hhi=round(sector_hhi, 6) if sector_hhi is not None else None,
        score=round(score, 1),
        grade=_grade(score),
        components=components,
    )


# --------------------------------------------------------------------------
# Allocation breakdowns
# --------------------------------------------------------------------------


def allocation_by(
    weights: dict[str, float], metadata: dict[str, SecurityMeta], field: str
) -> list[AllocationSlice]:
    """Group weights by a metadata field (sector, asset_class, country, ...)."""
    buckets: dict[str, list[str]] = {}
    totals: dict[str, float] = {}

    for ticker, weight in weights.items():
        meta = metadata.get(ticker)
        label = getattr(meta, field, None) if meta else None
        label = label or "Unknown"
        totals[label] = totals.get(label, 0.0) + weight
        buckets.setdefault(label, []).append(ticker)

    slices = [
        AllocationSlice(label=label, weight=round(weight, 6), tickers=sorted(buckets[label]))
        for label, weight in totals.items()
    ]
    slices.sort(key=lambda s: s.weight, reverse=True)
    return slices


def build_allocation(
    weights: dict[str, float], metadata: dict[str, SecurityMeta]
) -> dict[str, list[AllocationSlice]]:
    return {
        "by_ticker": [
            AllocationSlice(label=t, weight=round(w, 6), tickers=[t])
            for t, w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "by_sector": allocation_by(weights, metadata, "sector"),
        "by_asset_class": allocation_by(weights, metadata, "asset_class"),
        "by_country": allocation_by(weights, metadata, "country"),
        "by_industry": allocation_by(weights, metadata, "industry"),
    }


# --------------------------------------------------------------------------
# Opportunity detection
# --------------------------------------------------------------------------

# Thresholds that define "worth telling the user about". Collected here so the
# rules stay tunable in one place rather than scattered through the checks.
SINGLE_POSITION_LIMIT = 0.25
TOP5_LIMIT = 0.70
SECTOR_LIMIT = 0.40
SECTOR_OVERWEIGHT_PP = 0.15
REDUNDANT_CORRELATION = 0.85
MIN_EFFECTIVE_HOLDINGS = 8.0
HIGH_VOL_MULTIPLE = 1.35
DEEP_DRAWDOWN = -0.35
CASH_DRAG_LIMIT = 0.20


def detect_opportunities(
    weights: dict[str, float],
    metadata: dict[str, SecurityMeta],
    returns: pd.DataFrame,
    div: DiversificationMetrics,
    risk: RiskMetrics,
    benchmark_risk: RiskMetrics,
    benchmark: str,
) -> list[Opportunity]:
    """Turn the statistics into a ranked list of things worth acting on.

    These are observations about the shape of the allocation, not investment
    advice: each one names the metric that triggered it so the user can judge
    whether it matters for their situation.
    """
    found: list[Opportunity] = []

    def add(
        id_: str,
        severity: str,
        kind: str,
        title: str,
        detail: str,
        tickers: list[str] | None = None,
        metric: float | None = None,
    ) -> None:
        found.append(
            Opportunity(
                id=id_,
                severity=severity,  # type: ignore[arg-type]
                kind=kind,
                title=title,
                detail=detail,
                tickers=tickers or [],
                metric=metric,
            )
        )

    ordered = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)

    # --- Concentration ----------------------------------------------------
    if ordered and ordered[0][1] > SINGLE_POSITION_LIMIT:
        ticker, weight = ordered[0]
        add(
            "concentration-single",
            "critical" if weight > 0.40 else "warning",
            "concentration",
            f"{ticker} is {weight:.0%} of the portfolio",
            f"A single position above {SINGLE_POSITION_LIMIT:.0%} means the portfolio's "
            f"outcome is largely {ticker}'s outcome. Trimming toward "
            f"{SINGLE_POSITION_LIMIT:.0%} would cut single-name risk materially.",
            [ticker],
            round(weight, 4),
        )

    if div.top5_weight > TOP5_LIMIT and div.holdings_count > 5:
        add(
            "concentration-top5",
            "warning",
            "concentration",
            f"Top 5 positions are {div.top5_weight:.0%} of the book",
            f"The largest five holdings dominate. Effective holdings is "
            f"{div.effective_holdings:.1f} despite {div.holdings_count} positions -- the "
            f"smaller names are too small to change the outcome.",
            [t for t, _ in ordered[:5]],
            round(div.top5_weight, 4),
        )

    if div.effective_holdings < MIN_EFFECTIVE_HOLDINGS and div.holdings_count >= 3:
        add(
            "breadth-low",
            "warning",
            "diversification",
            f"Only {div.effective_holdings:.1f} effective holdings",
            f"{div.holdings_count} positions, but the weighting makes them behave like "
            f"{div.effective_holdings:.1f} equal-weight ones. More even sizing would "
            f"raise breadth without adding a single new ticker.",
            metric=round(div.effective_holdings, 2),
        )

    # --- Sector exposure --------------------------------------------------
    sector_weights: dict[str, float] = {}
    sector_tickers: dict[str, list[str]] = {}
    for ticker, weight in weights.items():
        meta = metadata.get(ticker)
        sector = (meta.sector if meta else None) or "Unknown"
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
        sector_tickers.setdefault(sector, []).append(ticker)

    for sector, weight in sorted(sector_weights.items(), key=lambda kv: -kv[1]):
        if sector in ("Unknown", "Diversified"):
            continue
        if weight > SECTOR_LIMIT:
            add(
                f"sector-heavy-{sector.lower().replace(' ', '-')}",
                "critical" if weight > 0.55 else "warning",
                "sector",
                f"{sector} is {weight:.0%} of the portfolio",
                f"Holdings in one sector move together in a sector-wide drawdown. "
                f"{', '.join(sorted(sector_tickers[sector]))} share that exposure.",
                sorted(sector_tickers[sector]),
                round(weight, 4),
            )
            break

    for sector, bench_weight in BENCHMARK_SECTOR_WEIGHTS.items():
        actual = sector_weights.get(sector, 0.0)
        gap = actual - bench_weight
        if gap > SECTOR_OVERWEIGHT_PP:
            add(
                f"sector-overweight-{sector.lower().replace(' ', '-')}",
                "info",
                "sector",
                f"{sector} is {gap * 100:.0f}pp above the broad market",
                f"You hold {actual:.0%} in {sector} versus roughly {bench_weight:.0%} for "
                f"the S&P 500. Intentional tilts are fine -- this flags it so it stays "
                f"a decision rather than an accident.",
                sorted(sector_tickers.get(sector, [])),
                round(gap, 4),
            )

    # --- Redundancy -------------------------------------------------------
    corr = correlation_matrix(returns)
    if not corr.empty:
        pairs: list[tuple[float, str, str]] = []
        cols = [c for c in corr.columns if c in weights]
        for i, a in enumerate(cols):
            for b in cols[i + 1 :]:
                rho = corr.loc[a, b]
                if pd.isna(rho):
                    continue
                if float(rho) >= REDUNDANT_CORRELATION:
                    pairs.append((float(rho), a, b))
        pairs.sort(reverse=True)
        for rho, a, b in pairs[:3]:
            combined = weights.get(a, 0.0) + weights.get(b, 0.0)
            add(
                f"redundant-{a}-{b}",
                "info",
                "redundancy",
                f"{a} and {b} move together ({rho:.2f} correlation)",
                f"These two behave almost identically, so holding both "
                f"({combined:.0%} combined) adds position count without adding "
                f"diversification. Consolidating frees room for an uncorrelated exposure.",
                [a, b],
                round(rho, 4),
            )

    if div.avg_correlation is not None and div.avg_correlation > 0.75:
        add(
            "correlation-high",
            "warning",
            "diversification",
            f"Average pairwise correlation is {div.avg_correlation:.2f}",
            "The holdings largely rise and fall together, so the portfolio carries "
            "roughly the risk of a single bet spread across several tickers. "
            "Assets with different drivers -- bonds, commodities, non-US equity -- "
            "are what lower this number.",
            metric=div.avg_correlation,
        )

    # --- Missing exposures ------------------------------------------------
    class_weights: dict[str, float] = {}
    for ticker, weight in weights.items():
        meta = metadata.get(ticker)
        cls = (meta.asset_class if meta else None) or "Unknown"
        class_weights[cls] = class_weights.get(cls, 0.0) + weight

    defensive = sum(w for c, w in class_weights.items() if c in DEFENSIVE_ASSET_CLASSES)
    if defensive < 0.05 and len(weights) >= 3:
        add(
            "no-ballast",
            "info",
            "allocation",
            "No bond, cash or commodity ballast",
            "The portfolio is effectively all growth assets, so there is nothing to "
            "cushion an equity drawdown or to rebalance from when prices fall. "
            "Even a small allocation changes the shape of the downside.",
            metric=round(defensive, 4),
        )

    countries = {
        (metadata.get(t).country if metadata.get(t) else "Unknown") for t in weights
    }
    non_us = sum(
        w
        for t, w in weights.items()
        if (metadata.get(t).country if metadata.get(t) else "Unknown")
        not in ("United States", "Unknown")
    )
    if non_us < 0.05 and len(countries) <= 2 and len(weights) >= 3:
        add(
            "home-bias",
            "info",
            "allocation",
            "Exposure is essentially all United States",
            "US assets are roughly 60% of global market capitalization. A portfolio "
            "with no international exposure is making an implicit bet that the US "
            "keeps outperforming.",
            metric=round(non_us, 4),
        )

    cash = class_weights.get("Cash", 0.0)
    if cash > CASH_DRAG_LIMIT:
        add(
            "cash-drag",
            "info",
            "allocation",
            f"{cash:.0%} sits in cash equivalents",
            "A large cash sleeve lowers volatility but also caps long-run return. "
            "Worth confirming this is a deliberate reserve rather than uninvested drift.",
            metric=round(cash, 4),
        )

    # --- Risk versus the benchmark ---------------------------------------
    if risk.annual_vol and benchmark_risk.annual_vol:
        ratio = risk.annual_vol / benchmark_risk.annual_vol
        if ratio > HIGH_VOL_MULTIPLE:
            add(
                "vol-high",
                "warning",
                "risk",
                f"Volatility is {ratio:.1f}x {benchmark}",
                f"Annualized volatility of {risk.annual_vol:.1%} against "
                f"{benchmark_risk.annual_vol:.1%} for {benchmark}. Confirm the extra "
                f"return has been worth the extra swing -- compare the Sharpe ratios.",
                metric=round(ratio, 3),
            )

    if risk.max_drawdown is not None and risk.max_drawdown < DEEP_DRAWDOWN:
        add(
            "drawdown-deep",
            "warning",
            "risk",
            f"Worst drawdown was {risk.max_drawdown:.0%}",
            "Over this window the portfolio fell that far below its peak. The useful "
            "question is whether you would have held through it without selling.",
            metric=round(risk.max_drawdown, 4),
        )

    if (
        risk.sharpe is not None
        and benchmark_risk.sharpe is not None
        and risk.sharpe < benchmark_risk.sharpe - 0.2
    ):
        add(
            "risk-adjusted-lag",
            "warning",
            "performance",
            f"Risk-adjusted return trails {benchmark}",
            f"Sharpe ratio of {risk.sharpe:.2f} against {benchmark_risk.sharpe:.2f} for "
            f"{benchmark}. The portfolio took on risk it was not paid for over this window.",
            metric=round(risk.sharpe - benchmark_risk.sharpe, 4),
        )

    if div.score >= 80 and not any(o.severity in ("warning", "critical") for o in found):
        add(
            "well-diversified",
            "info",
            "diversification",
            f"Well diversified (score {div.score:.0f}/100, grade {div.grade})",
            "No concentration, correlation or sector flags triggered. The main lever "
            "from here is cost and tax efficiency rather than allocation.",
            metric=div.score,
        )

    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    found.sort(key=lambda o: (severity_rank[o.severity], -(o.metric or 0)))
    return found


# --------------------------------------------------------------------------
# Assembly helpers
# --------------------------------------------------------------------------


def build_holdings(
    weights: dict[str, float],
    metadata: dict[str, SecurityMeta],
    prices: pd.DataFrame,
    returns: pd.DataFrame,
) -> list[HoldingDetail]:
    """Per-position detail, including return and risk contribution."""
    risk_shares, marginals = risk_contributions(returns, weights)
    details: list[HoldingDetail] = []

    for ticker, weight in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        meta = metadata.get(ticker) or SecurityMeta(ticker=ticker)
        series = returns[ticker] if ticker in returns.columns else pd.Series(dtype=float)

        total_return = float((1.0 + series).prod() - 1.0) if not series.empty else None
        vol = (
            float(series.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(series) > 1 else None
        )
        last_price = (
            float(prices[ticker].dropna().iloc[-1])
            if ticker in prices.columns and not prices[ticker].dropna().empty
            else None
        )

        details.append(
            HoldingDetail(
                **meta.model_dump(),
                weight=round(weight, 6),
                last_price=last_price,
                return_1y=total_return,
                annual_vol=vol,
                contribution_to_return=(
                    round(weight * total_return, 6) if total_return is not None else None
                ),
                contribution_to_risk=(
                    round(risk_shares[ticker], 6) if ticker in risk_shares else None
                ),
                marginal_risk=(
                    round(marginals[ticker], 6) if ticker in marginals else None
                ),
            )
        )
    return details


def build_series(
    portfolio: pd.Series, benchmark: pd.Series | None
) -> tuple[list[SeriesPoint], list[DrawdownPoint]]:
    """Growth-of-100 curves and the portfolio drawdown path."""
    if portfolio.empty:
        return [], []

    port_curve = growth_curve(portfolio)
    bench_curve = growth_curve(benchmark) if benchmark is not None and not benchmark.empty else None
    dd = drawdown_series(portfolio)

    points: list[SeriesPoint] = []
    for idx, value in port_curve.items():
        day: date = idx.date() if hasattr(idx, "date") else idx
        bench_value = None
        if bench_curve is not None and idx in bench_curve.index:
            bench_value = round(float(bench_curve.loc[idx]), 4)
        points.append(
            SeriesPoint(date=day, portfolio=round(float(value), 4), benchmark=bench_value)
        )

    drawdowns = [
        DrawdownPoint(
            date=idx.date() if hasattr(idx, "date") else idx,
            drawdown=round(float(value), 6),
        )
        for idx, value in dd.items()
    ]
    return points, drawdowns


def build_correlation(returns: pd.DataFrame, tickers: list[str]) -> CorrelationMatrix:
    corr = correlation_matrix(returns)
    cols = [t for t in tickers if t in corr.columns]
    matrix: list[list[float | None]] = []
    for a in cols:
        row: list[float | None] = []
        for b in cols:
            value = corr.loc[a, b] if a in corr.index and b in corr.columns else None
            row.append(None if value is None or pd.isna(value) else round(float(value), 4))
        matrix.append(row)
    return CorrelationMatrix(tickers=cols, matrix=matrix)
