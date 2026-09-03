"""Provider registry and the fallback chain used by the API.

Order of preference when ``provider="auto"``:

    openbb  ->  yfinance  ->  demo

OpenBB first because it fronts the highest-quality vendors, yfinance as a
zero-config fallback, and the offline demo source last so the app always
returns something rather than an error page.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from app.providers.base import MarketDataProvider, ProviderError
from app.providers.demo import DemoProvider
from app.providers.openbb_provider import OpenBBProvider
from app.providers.yahoo import YFinanceProvider
from app.schemas import SecurityMeta

log = logging.getLogger(__name__)

CHAIN: list[MarketDataProvider] = [OpenBBProvider(), YFinanceProvider(), DemoProvider()]
REGISTRY: dict[str, MarketDataProvider] = {p.name: p for p in CHAIN}


def availability() -> dict[str, bool]:
    return {p.name: p.available() for p in CHAIN}


def resolve(preference: str = "auto") -> list[MarketDataProvider]:
    """Return the ordered list of providers to try for a request."""
    preference = (preference or "auto").strip().lower()
    if preference in ("", "auto"):
        return [p for p in CHAIN if p.available()]

    chosen = REGISTRY.get(preference)
    if chosen is None:
        raise ValueError(
            f"Unknown provider '{preference}'. Options: auto, {', '.join(REGISTRY)}"
        )
    if not chosen.available():
        raise ProviderError(
            f"Provider '{preference}' is not installed. "
            f"Install it with: pip install -e 'api[{preference}]'"
        )
    # An explicit choice still falls back to demo so the UI stays usable.
    return [chosen] if preference == "demo" else [chosen, DemoProvider()]


class ProviderResult:
    """Prices and metadata plus a record of how they were obtained."""

    def __init__(
        self,
        prices: pd.DataFrame,
        metadata: dict[str, SecurityMeta],
        provider: str,
        warnings: list[str],
    ) -> None:
        self.prices = prices
        self.metadata = metadata
        self.provider = provider
        self.warnings = warnings


def fetch(
    tickers: list[str], start: date, end: date, preference: str = "auto"
) -> ProviderResult:
    """Walk the provider chain until one returns usable price history."""
    warnings: list[str] = []
    chain = resolve(preference)
    if not chain:
        raise ProviderError("No market data provider is available")

    for provider in chain:
        try:
            prices = provider.fetch_prices(tickers, start, end)
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            log.warning("Provider %s failed: %s", provider.name, exc)
            warnings.append(f"{provider.name}: {exc}")
            continue

        prices = prices.dropna(axis=1, how="all")
        if prices.empty or prices.shape[1] == 0:
            warnings.append(f"{provider.name}: returned no usable columns")
            continue

        missing = [t for t in tickers if t not in prices.columns]
        if missing:
            warnings.append(
                f"{provider.name}: no history for {', '.join(missing)}"
            )

        try:
            metadata = provider.fetch_metadata(list(prices.columns))
        except Exception as exc:  # noqa: BLE001 - metadata is non-fatal
            log.warning("Provider %s metadata failed: %s", provider.name, exc)
            warnings.append(f"{provider.name} metadata: {exc}")
            from app.providers.base import reference_metadata

            metadata = {t: reference_metadata(t) for t in prices.columns}

        return ProviderResult(prices, metadata, provider.name, warnings)

    raise ProviderError(
        "Every provider failed. Details: " + " | ".join(warnings)
    )


__all__ = [
    "CHAIN",
    "REGISTRY",
    "ProviderError",
    "ProviderResult",
    "availability",
    "fetch",
    "resolve",
]
