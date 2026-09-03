"""Populate the warehouse with example portfolios.

Run with ``make seed`` (or ``python -m app.seed``) to give the dbt models
something to build on before you have analyzed anything through the UI.
"""

from __future__ import annotations

import argparse

from app.schemas import AnalyzeRequest
from app.service import analyze

EXAMPLES: list[tuple[str, list[tuple[str, float]]]] = [
    ("Three-fund", [("VTI", 50), ("VXUS", 30), ("BND", 20)]),
    ("60/40", [("VOO", 60), ("BND", 40)]),
    ("All weather", [("VTI", 30), ("TLT", 40), ("SHY", 15), ("GLD", 7.5), ("DBC", 7.5)]),
    ("Big tech", [("AAPL", 20), ("MSFT", 20), ("NVDA", 20), ("GOOGL", 20), ("AMZN", 20)]),
    (
        "Dividend income",
        [("SCHD", 35), ("VYM", 25), ("VNQ", 15), ("LQD", 15), ("TIP", 10)],
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        default="auto",
        help="Market data provider: auto, openbb, yfinance or demo.",
    )
    parser.add_argument(
        "--lookback-days", type=int, default=1095, help="History window to fetch."
    )
    args = parser.parse_args()

    for label, holdings in EXAMPLES:
        request = AnalyzeRequest(
            label=label,
            holdings=[{"ticker": t, "weight": w} for t, w in holdings],  # type: ignore[list-item]
            provider=args.provider,
            lookback_days=args.lookback_days,
        )
        result = analyze(request, persist=True)
        print(
            f"{label:<18} {result.data_quality.provider:<9} "
            f"{result.data_quality.observations:>4} days  "
            f"diversification {result.diversification.score:>5.1f} "
            f"({result.diversification.grade})"
        )

    print("\nWarehouse seeded. Build the models with: make dbt")


if __name__ == "__main__":
    main()
