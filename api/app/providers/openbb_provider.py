"""OpenBB-backed provider.

OpenBB is the preferred source: one interface in front of many vendors
(FMP, Intrinio, Polygon, Tiingo, ...), so upgrading data quality is a matter of
configuring credentials rather than changing this code.

Install with ``pip install -e 'api[openbb]'``. Without credentials OpenBB
still serves its free default vendors, which is enough for daily closes.
"""

from __future__ import annotations

import logging
import os
from datetime import date

import pandas as pd

from app.providers.base import ProviderError, merge_metadata, reference_metadata
from app.schemas import SecurityMeta

log = logging.getLogger(__name__)

# Vendor OpenBB should route to. Override with PORTFOLIO_OPENBB_VENDOR.
_DEFAULT_VENDOR = os.getenv("PORTFOLIO_OPENBB_VENDOR", "yfinance")


class OpenBBProvider:
    name = "openbb"

    def available(self) -> bool:
        try:
            from openbb import obb  # noqa: F401
        except Exception:  # noqa: BLE001 - OpenBB import can fail many ways
            return False
        return True

    def _obb(self):
        try:
            from openbb import obb
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("OpenBB is not installed or failed to import") from exc
        return obb

    def fetch_prices(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        obb = self._obb()
        frames: list[pd.Series] = []
        failures: list[str] = []

        for ticker in tickers:
            try:
                result = obb.equity.price.historical(
                    symbol=ticker,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    provider=_DEFAULT_VENDOR,
                )
                df = result.to_df()
            except Exception as exc:  # noqa: BLE001 - one bad symbol must not fail all
                log.warning("OpenBB history failed for %s: %s", ticker, exc)
                failures.append(ticker)
                continue

            if df is None or df.empty:
                failures.append(ticker)
                continue

            # OpenBB returns adjusted close when the vendor supplies it.
            column = next(
                (c for c in ("adj_close", "close", "Close") if c in df.columns), None
            )
            if column is None:
                failures.append(ticker)
                continue

            series = df[column].copy()
            series.index = pd.DatetimeIndex(series.index).tz_localize(None)
            series.name = ticker
            frames.append(series)

        if not frames:
            raise ProviderError(
                f"OpenBB returned no usable history (failed: {', '.join(failures) or 'all'})"
            )

        prices = pd.concat(frames, axis=1).sort_index()
        prices.index.name = "date"
        return prices

    def fetch_metadata(self, tickers: list[str]) -> dict[str, SecurityMeta]:
        obb = self._obb()
        out: dict[str, SecurityMeta] = {}

        for ticker in tickers:
            fallback = reference_metadata(ticker)
            try:
                profile = obb.equity.profile(symbol=ticker, provider=_DEFAULT_VENDOR).to_df()
            except Exception as exc:  # noqa: BLE001 - metadata is best-effort
                log.info("OpenBB profile unavailable for %s: %s", ticker, exc)
                out[ticker] = fallback
                continue

            if profile is None or profile.empty:
                out[ticker] = fallback
                continue

            row = profile.iloc[0].to_dict()
            live = SecurityMeta(
                ticker=ticker,
                name=_first(row, "name", "long_name", "company_name"),
                sector=_first(row, "sector") or "Unknown",
                industry=_first(row, "industry", "industry_category") or "Unknown",
                country=_first(row, "country", "hq_country") or "Unknown",
                asset_class=_first(row, "asset_class") or "Unknown",
                currency=_first(row, "currency") or "USD",
                market_cap=_as_float(row.get("market_cap")),
                pe_ratio=_as_float(row.get("pe_ratio") or row.get("price_to_earnings")),
                dividend_yield=_as_float(row.get("dividend_yield")),
                beta=_as_float(row.get("beta")),
            )
            out[ticker] = merge_metadata(live, fallback)
        return out


def _first(row: dict, *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if out != out else out
