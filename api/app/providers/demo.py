"""Offline provider that synthesizes plausible price history.

The app must be fully explorable with no network and no API keys, so this
provider generates geometric Brownian motion per ticker, seeded deterministically
from the ticker symbol. Prices are stable across runs, correlated through a
shared market factor, and calibrated to each security's reference drift/vol.

These are simulated numbers. They are never presented as real market data --
the API tags every response with the provider that served it, and the UI
displays a banner whenever ``demo`` is active.
"""

from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pandas as pd

from app.providers.base import business_days, reference_metadata
from app.reference import lookup
from app.schemas import SecurityMeta

# How much of each asset's move comes from the common market factor. Without
# this the synthetic correlation matrix would be pure noise and the
# diversification analytics would look unrealistically good.
_MARKET_BETA_DEFAULT = 0.65


def _seed(ticker: str) -> int:
    digest = hashlib.sha256(ticker.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


class DemoProvider:
    name = "demo"

    def available(self) -> bool:
        return True

    def fetch_prices(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        index = business_days(start, end)
        n = len(index)
        if n == 0:
            return pd.DataFrame(index=pd.DatetimeIndex([], name="date"))

        # One shared market factor drives cross-asset correlation.
        market_rng = np.random.default_rng(_seed("__MARKET__"))
        market = market_rng.normal(0.0, 1.0, n)

        frame = pd.DataFrame(index=index)
        for ticker in tickers:
            ref = lookup(ticker)
            drift = ref.drift if ref else 0.07
            vol = ref.vol if ref else 0.28
            asset_class = ref.asset_class if ref else "Equity"

            # Bonds, cash and commodities track equities only loosely.
            if asset_class in {"Bond ETF", "Cash"}:
                beta = 0.05
            elif asset_class in {"Commodity", "Crypto"}:
                beta = 0.25
            else:
                beta = _MARKET_BETA_DEFAULT

            rng = np.random.default_rng(_seed(ticker))
            idio = rng.normal(0.0, 1.0, n)
            shocks = beta * market + np.sqrt(max(1.0 - beta**2, 0.0)) * idio

            dt = 1.0 / 252.0
            daily = (drift - 0.5 * vol**2) * dt + vol * np.sqrt(dt) * shocks
            prices = 100.0 * np.exp(np.cumsum(daily))
            frame[ticker] = prices

        frame.index.name = "date"
        return frame

    def fetch_metadata(self, tickers: list[str]) -> dict[str, SecurityMeta]:
        out: dict[str, SecurityMeta] = {}
        for ticker in tickers:
            meta = reference_metadata(ticker)
            ref = lookup(ticker)
            if ref is not None:
                # Deterministic but clearly synthetic fundamentals.
                rng = np.random.default_rng(_seed(ticker))
                if ref.asset_class == "Equity":
                    meta.pe_ratio = round(float(rng.uniform(12, 45)), 1)
                    meta.market_cap = float(rng.uniform(2e10, 3e12))
                    meta.dividend_yield = round(float(rng.uniform(0, 0.035)), 4)
                meta.beta = round(float(ref.vol / 0.16), 2)
            out[ticker] = meta
        return out
