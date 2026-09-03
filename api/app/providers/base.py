"""Provider interface shared by every market-data source."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from app.reference import lookup
from app.schemas import SecurityMeta


class ProviderError(RuntimeError):
    """Raised when a provider is installed but cannot service a request."""


@runtime_checkable
class MarketDataProvider(Protocol):
    """Minimal surface every source must implement.

    Keeping this narrow is what lets OpenBB, yfinance and the offline demo
    source be swapped without the analytics layer knowing the difference.
    """

    name: str

    def available(self) -> bool:
        """True when the provider's dependencies and credentials are present."""

    def fetch_prices(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        """Adjusted close prices: a DatetimeIndex by date, one column per ticker.

        Tickers that cannot be resolved are omitted from the columns rather
        than raising, so one bad symbol never sinks the whole request.
        """

    def fetch_metadata(self, tickers: list[str]) -> dict[str, SecurityMeta]:
        """Descriptive and fundamental data, keyed by ticker."""


def reference_metadata(ticker: str) -> SecurityMeta:
    """Fall back to the static universe, then to an 'Unknown' placeholder."""
    ref = lookup(ticker)
    if ref is None:
        return SecurityMeta(ticker=ticker.upper())
    return SecurityMeta(
        ticker=ref.ticker,
        name=ref.name,
        sector=ref.sector,
        industry=ref.industry,
        country=ref.country,
        asset_class=ref.asset_class,
        currency=ref.currency,
    )


def merge_metadata(primary: SecurityMeta, fallback: SecurityMeta) -> SecurityMeta:
    """Overlay ``primary`` onto ``fallback``, ignoring empty/unknown fields."""
    merged = fallback.model_dump()
    for key, value in primary.model_dump().items():
        if value in (None, "", "Unknown"):
            continue
        merged[key] = value
    return SecurityMeta(**merged)


def business_days(start: date, end: date) -> pd.DatetimeIndex:
    """Weekday calendar. Close enough for analytics; holidays add no bias here."""
    return pd.bdate_range(start=start, end=end)
