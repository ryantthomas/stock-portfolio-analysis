"""Pydantic models describing the API contract shared with the React client."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Severity = Literal["info", "warning", "critical"]


class HoldingInput(BaseModel):
    """A single position as entered by the user: a ticker and its target weight."""

    ticker: str = Field(..., min_length=1, max_length=16)
    weight: float = Field(..., ge=0, le=1000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()


class AnalyzeRequest(BaseModel):
    holdings: list[HoldingInput] = Field(..., min_length=1, max_length=100)
    benchmark: str = "SPY"
    lookback_days: int = Field(1095, ge=90, le=7300)
    provider: str = "auto"
    # Weights are accepted either as percentages (sum ~100) or decimals (sum ~1).
    normalize: bool = True

    @field_validator("benchmark")
    @classmethod
    def normalize_benchmark(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def check_duplicates(self) -> AnalyzeRequest:
        seen = [h.ticker for h in self.holdings]
        dupes = {t for t in seen if seen.count(t) > 1}
        if dupes:
            raise ValueError(f"Duplicate tickers: {', '.join(sorted(dupes))}")
        if sum(h.weight for h in self.holdings) <= 0:
            raise ValueError("Total weight must be greater than zero")
        return self

    def normalized_weights(self) -> dict[str, float]:
        """Return weights rescaled to sum to 1.0."""
        total = sum(h.weight for h in self.holdings)
        return {h.ticker: h.weight / total for h in self.holdings}


class SecurityMeta(BaseModel):
    ticker: str
    name: str | None = None
    sector: str = "Unknown"
    industry: str = "Unknown"
    country: str = "Unknown"
    asset_class: str = "Equity"
    currency: str = "USD"
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None


class HoldingDetail(SecurityMeta):
    weight: float
    last_price: float | None = None
    return_1y: float | None = None
    annual_vol: float | None = None
    contribution_to_return: float | None = None
    contribution_to_risk: float | None = None
    # Marginal contribution to risk: d(portfolio vol)/d(weight).
    marginal_risk: float | None = None


class AllocationSlice(BaseModel):
    label: str
    weight: float
    tickers: list[str] = []


class RiskMetrics(BaseModel):
    annual_return: float | None = None
    annual_vol: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    beta: float | None = None
    alpha: float | None = None
    tracking_error: float | None = None
    var_95: float | None = None
    cvar_95: float | None = None
    best_day: float | None = None
    worst_day: float | None = None
    positive_days: float | None = None


class DiversificationMetrics(BaseModel):
    """How genuinely spread out the portfolio is, beyond just counting positions."""

    holdings_count: int
    # Herfindahl-Hirschman Index of the weights: 1.0 = everything in one name.
    hhi: float
    # 1 / HHI -- the number of equal-weight positions that would be as concentrated.
    effective_holdings: float
    top_weight: float
    top5_weight: float
    avg_correlation: float | None = None
    # Weighted-average asset vol divided by portfolio vol. Higher = more benefit.
    diversification_ratio: float | None = None
    sector_count: int = 0
    sector_hhi: float | None = None
    # 0-100 composite of the components above.
    score: float = 0.0
    grade: str = "n/a"
    components: dict[str, float] = {}


class Opportunity(BaseModel):
    """An actionable observation surfaced to the user."""

    id: str
    severity: Severity
    kind: str
    title: str
    detail: str
    tickers: list[str] = []
    metric: float | None = None


class SeriesPoint(BaseModel):
    date: date
    portfolio: float
    benchmark: float | None = None


class DrawdownPoint(BaseModel):
    date: date
    drawdown: float


class CorrelationMatrix(BaseModel):
    tickers: list[str]
    matrix: list[list[float | None]]


class DataQuality(BaseModel):
    provider: str
    requested: list[str]
    resolved: list[str]
    missing: list[str] = []
    warnings: list[str] = []
    history_start: date | None = None
    history_end: date | None = None
    observations: int = 0


class AnalyzeResponse(BaseModel):
    as_of: date | None = None
    benchmark: str
    data_quality: DataQuality
    holdings: list[HoldingDetail]
    allocation: dict[str, list[AllocationSlice]]
    performance: list[SeriesPoint]
    drawdown: list[DrawdownPoint]
    risk: RiskMetrics
    benchmark_risk: RiskMetrics
    diversification: DiversificationMetrics
    correlation: CorrelationMatrix
    opportunities: list[Opportunity]


class SearchResult(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    asset_class: str | None = None


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, bool]
    active_provider: str
    warehouse: dict[str, object]
