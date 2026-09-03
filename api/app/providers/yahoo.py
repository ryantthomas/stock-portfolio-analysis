"""yfinance-backed provider.

Free, no API key, and good enough for daily closes on equities, ETFs and
crypto. Installed via the ``yfinance`` optional dependency group.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from app.providers.base import ProviderError, merge_metadata, reference_metadata
from app.schemas import SecurityMeta

log = logging.getLogger(__name__)


class YFinanceProvider:
    name = "yfinance"

    def available(self) -> bool:
        try:
            import yfinance  # noqa: F401
        except ImportError:
            return False
        return True

    def fetch_prices(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - guarded by available()
            raise ProviderError("yfinance is not installed") from exc

        # yfinance treats `end` as exclusive.
        raw = yf.download(
            tickers=" ".join(tickers),
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="column",
        )
        if raw is None or raw.empty:
            raise ProviderError("yfinance returned no rows")

        # Single-ticker downloads come back with flat columns; multi-ticker
        # downloads come back with a (field, ticker) MultiIndex.
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" not in raw.columns.get_level_values(0):
                raise ProviderError("yfinance response had no Close column")
            close = raw["Close"].copy()
        else:
            if "Close" not in raw.columns:
                raise ProviderError("yfinance response had no Close column")
            close = raw[["Close"]].copy()
            close.columns = [tickers[0]]

        close = close.dropna(axis=1, how="all")
        close.index = pd.DatetimeIndex(close.index).tz_localize(None)
        close.index.name = "date"
        return close.sort_index()

    def fetch_metadata(self, tickers: list[str]) -> dict[str, SecurityMeta]:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("yfinance is not installed") from exc

        out: dict[str, SecurityMeta] = {}
        for ticker in tickers:
            fallback = reference_metadata(ticker)
            try:
                info = yf.Ticker(ticker).get_info() or {}
            except Exception as exc:  # noqa: BLE001 - metadata is best-effort
                log.warning("yfinance metadata failed for %s: %s", ticker, exc)
                out[ticker] = fallback
                continue

            quote_type = str(info.get("quoteType") or "").upper()
            asset_class = {
                "ETF": "Equity ETF",
                "MUTUALFUND": "Fund",
                "CRYPTOCURRENCY": "Crypto",
                "CURRENCY": "Currency",
                "INDEX": "Index",
            }.get(quote_type, "Equity")

            live = SecurityMeta(
                ticker=ticker,
                name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector") or "Unknown",
                industry=info.get("industry") or "Unknown",
                country=info.get("country") or "Unknown",
                asset_class=asset_class if quote_type else "Unknown",
                currency=info.get("currency") or "USD",
                market_cap=_as_float(info.get("marketCap")),
                pe_ratio=_as_float(info.get("trailingPE")),
                dividend_yield=_as_float(info.get("dividendYield")),
                beta=_as_float(info.get("beta")),
            )
            out[ticker] = merge_metadata(live, fallback)
        return out


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if out != out else out  # drop NaN
