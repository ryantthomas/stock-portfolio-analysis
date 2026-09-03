"""A static reference universe of widely held tickers.

This serves three purposes:

1. Ticker autocomplete in the UI without a network round trip.
2. Sector/asset-class metadata when a live provider returns prices but no
   fundamentals (common for ETFs).
3. Plausible metadata for the offline ``demo`` provider so the app is fully
   explorable with no API keys and no network.

Live providers always win: anything they return overrides these values.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceSecurity:
    ticker: str
    name: str
    sector: str
    industry: str
    country: str
    asset_class: str
    # Annualized drift and vol used only by the offline demo price generator.
    drift: float = 0.08
    vol: float = 0.25
    currency: str = "USD"


def _s(*args, **kwargs) -> ReferenceSecurity:
    return ReferenceSecurity(*args, **kwargs)


_UNIVERSE: list[ReferenceSecurity] = [
    # --- Mega-cap technology -------------------------------------------------
    _s("AAPL", "Apple Inc.", "Technology", "Consumer Electronics", "United States", "Equity", 0.18, 0.28),
    _s("MSFT", "Microsoft Corporation", "Technology", "Software - Infrastructure", "United States", "Equity", 0.20, 0.26),
    _s("GOOGL", "Alphabet Inc. Class A", "Communication Services", "Internet Content & Information", "United States", "Equity", 0.17, 0.30),
    _s("GOOG", "Alphabet Inc. Class C", "Communication Services", "Internet Content & Information", "United States", "Equity", 0.17, 0.30),
    _s("AMZN", "Amazon.com Inc.", "Consumer Cyclical", "Internet Retail", "United States", "Equity", 0.16, 0.33),
    _s("META", "Meta Platforms Inc.", "Communication Services", "Internet Content & Information", "United States", "Equity", 0.19, 0.38),
    _s("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors", "United States", "Equity", 0.35, 0.50),
    _s("AVGO", "Broadcom Inc.", "Technology", "Semiconductors", "United States", "Equity", 0.25, 0.38),
    _s("AMD", "Advanced Micro Devices", "Technology", "Semiconductors", "United States", "Equity", 0.20, 0.48),
    _s("INTC", "Intel Corporation", "Technology", "Semiconductors", "United States", "Equity", 0.02, 0.36),
    _s("TSM", "Taiwan Semiconductor ADR", "Technology", "Semiconductors", "Taiwan", "Equity", 0.18, 0.34),
    _s("ORCL", "Oracle Corporation", "Technology", "Software - Infrastructure", "United States", "Equity", 0.15, 0.29),
    _s("CRM", "Salesforce Inc.", "Technology", "Software - Application", "United States", "Equity", 0.12, 0.33),
    _s("ADBE", "Adobe Inc.", "Technology", "Software - Application", "United States", "Equity", 0.11, 0.32),
    _s("NFLX", "Netflix Inc.", "Communication Services", "Entertainment", "United States", "Equity", 0.18, 0.36),
    _s("TSLA", "Tesla Inc.", "Consumer Cyclical", "Auto Manufacturers", "United States", "Equity", 0.20, 0.55),
    _s("PLTR", "Palantir Technologies", "Technology", "Software - Infrastructure", "United States", "Equity", 0.30, 0.55),
    _s("SHOP", "Shopify Inc.", "Technology", "Software - Application", "Canada", "Equity", 0.15, 0.45),
    _s("UBER", "Uber Technologies", "Technology", "Software - Application", "United States", "Equity", 0.16, 0.38),

    # --- Financials ----------------------------------------------------------
    _s("BRK-B", "Berkshire Hathaway Class B", "Financial Services", "Insurance - Diversified", "United States", "Equity", 0.11, 0.18),
    _s("JPM", "JPMorgan Chase & Co.", "Financial Services", "Banks - Diversified", "United States", "Equity", 0.12, 0.24),
    _s("BAC", "Bank of America Corp.", "Financial Services", "Banks - Diversified", "United States", "Equity", 0.09, 0.28),
    _s("GS", "Goldman Sachs Group", "Financial Services", "Capital Markets", "United States", "Equity", 0.11, 0.27),
    _s("V", "Visa Inc.", "Financial Services", "Credit Services", "United States", "Equity", 0.13, 0.21),
    _s("MA", "Mastercard Inc.", "Financial Services", "Credit Services", "United States", "Equity", 0.14, 0.22),
    _s("AXP", "American Express Co.", "Financial Services", "Credit Services", "United States", "Equity", 0.12, 0.26),

    # --- Healthcare ----------------------------------------------------------
    _s("UNH", "UnitedHealth Group", "Healthcare", "Healthcare Plans", "United States", "Equity", 0.10, 0.26),
    _s("JNJ", "Johnson & Johnson", "Healthcare", "Drug Manufacturers - General", "United States", "Equity", 0.06, 0.17),
    _s("LLY", "Eli Lilly and Company", "Healthcare", "Drug Manufacturers - General", "United States", "Equity", 0.25, 0.30),
    _s("PFE", "Pfizer Inc.", "Healthcare", "Drug Manufacturers - General", "United States", "Equity", 0.02, 0.24),
    _s("ABBV", "AbbVie Inc.", "Healthcare", "Drug Manufacturers - General", "United States", "Equity", 0.11, 0.22),
    _s("TMO", "Thermo Fisher Scientific", "Healthcare", "Diagnostics & Research", "United States", "Equity", 0.09, 0.24),

    # --- Consumer ------------------------------------------------------------
    _s("WMT", "Walmart Inc.", "Consumer Defensive", "Discount Stores", "United States", "Equity", 0.12, 0.20),
    _s("COST", "Costco Wholesale Corp.", "Consumer Defensive", "Discount Stores", "United States", "Equity", 0.15, 0.21),
    _s("PG", "Procter & Gamble Co.", "Consumer Defensive", "Household & Personal Products", "United States", "Equity", 0.07, 0.16),
    _s("KO", "Coca-Cola Company", "Consumer Defensive", "Beverages - Non-Alcoholic", "United States", "Equity", 0.06, 0.16),
    _s("PEP", "PepsiCo Inc.", "Consumer Defensive", "Beverages - Non-Alcoholic", "United States", "Equity", 0.06, 0.16),
    _s("MCD", "McDonald's Corporation", "Consumer Cyclical", "Restaurants", "United States", "Equity", 0.10, 0.18),
    _s("NKE", "NIKE Inc.", "Consumer Cyclical", "Footwear & Accessories", "United States", "Equity", 0.04, 0.28),
    _s("HD", "Home Depot Inc.", "Consumer Cyclical", "Home Improvement Retail", "United States", "Equity", 0.11, 0.23),

    # --- Industrials / Energy / Materials / Utilities ------------------------
    _s("CAT", "Caterpillar Inc.", "Industrials", "Farm & Heavy Construction Machinery", "United States", "Equity", 0.13, 0.27),
    _s("BA", "Boeing Company", "Industrials", "Aerospace & Defense", "United States", "Equity", 0.03, 0.38),
    _s("GE", "GE Aerospace", "Industrials", "Aerospace & Defense", "United States", "Equity", 0.16, 0.30),
    _s("XOM", "Exxon Mobil Corporation", "Energy", "Oil & Gas Integrated", "United States", "Equity", 0.10, 0.28),
    _s("CVX", "Chevron Corporation", "Energy", "Oil & Gas Integrated", "United States", "Equity", 0.09, 0.26),
    _s("LIN", "Linde plc", "Basic Materials", "Specialty Chemicals", "United Kingdom", "Equity", 0.12, 0.21),
    _s("NEE", "NextEra Energy Inc.", "Utilities", "Utilities - Regulated Electric", "United States", "Equity", 0.07, 0.24),
    _s("DUK", "Duke Energy Corporation", "Utilities", "Utilities - Regulated Electric", "United States", "Equity", 0.05, 0.19),
    _s("AMT", "American Tower Corp.", "Real Estate", "REIT - Specialty", "United States", "Equity", 0.05, 0.25),
    _s("PLD", "Prologis Inc.", "Real Estate", "REIT - Industrial", "United States", "Equity", 0.07, 0.26),

    # --- Broad-market and factor ETFs ---------------------------------------
    _s("SPY", "SPDR S&P 500 ETF Trust", "Diversified", "US Large Blend", "United States", "Equity ETF", 0.10, 0.16),
    _s("VOO", "Vanguard S&P 500 ETF", "Diversified", "US Large Blend", "United States", "Equity ETF", 0.10, 0.16),
    _s("IVV", "iShares Core S&P 500 ETF", "Diversified", "US Large Blend", "United States", "Equity ETF", 0.10, 0.16),
    _s("VTI", "Vanguard Total Stock Market ETF", "Diversified", "US Total Market", "United States", "Equity ETF", 0.10, 0.17),
    _s("QQQ", "Invesco QQQ Trust", "Diversified", "US Large Growth", "United States", "Equity ETF", 0.14, 0.22),
    _s("IWM", "iShares Russell 2000 ETF", "Diversified", "US Small Blend", "United States", "Equity ETF", 0.07, 0.23),
    _s("DIA", "SPDR Dow Jones Industrial Average ETF", "Diversified", "US Large Value", "United States", "Equity ETF", 0.09, 0.16),
    _s("VTV", "Vanguard Value ETF", "Diversified", "US Large Value", "United States", "Equity ETF", 0.09, 0.15),
    _s("VUG", "Vanguard Growth ETF", "Diversified", "US Large Growth", "United States", "Equity ETF", 0.13, 0.21),
    _s("SCHD", "Schwab US Dividend Equity ETF", "Diversified", "US Dividend", "United States", "Equity ETF", 0.09, 0.15),
    _s("VYM", "Vanguard High Dividend Yield ETF", "Diversified", "US Dividend", "United States", "Equity ETF", 0.08, 0.15),
    _s("MTUM", "iShares MSCI USA Momentum Factor ETF", "Diversified", "US Momentum", "United States", "Equity ETF", 0.11, 0.19),

    # --- International ETFs --------------------------------------------------
    _s("VXUS", "Vanguard Total International Stock ETF", "Diversified", "International Blend", "Global ex-US", "Equity ETF", 0.06, 0.16),
    _s("VEA", "Vanguard FTSE Developed Markets ETF", "Diversified", "Developed Markets", "Global ex-US", "Equity ETF", 0.06, 0.16),
    _s("VWO", "Vanguard FTSE Emerging Markets ETF", "Diversified", "Emerging Markets", "Emerging Markets", "Equity ETF", 0.05, 0.20),
    _s("EFA", "iShares MSCI EAFE ETF", "Diversified", "Developed Markets", "Global ex-US", "Equity ETF", 0.06, 0.17),
    _s("IEMG", "iShares Core MSCI Emerging Markets ETF", "Diversified", "Emerging Markets", "Emerging Markets", "Equity ETF", 0.05, 0.19),

    # --- Sector ETFs ---------------------------------------------------------
    _s("XLK", "Technology Select Sector SPDR", "Technology", "Sector Fund", "United States", "Equity ETF", 0.16, 0.23),
    _s("XLF", "Financial Select Sector SPDR", "Financial Services", "Sector Fund", "United States", "Equity ETF", 0.10, 0.21),
    _s("XLE", "Energy Select Sector SPDR", "Energy", "Sector Fund", "United States", "Equity ETF", 0.08, 0.29),
    _s("XLV", "Health Care Select Sector SPDR", "Healthcare", "Sector Fund", "United States", "Equity ETF", 0.08, 0.17),
    _s("XLU", "Utilities Select Sector SPDR", "Utilities", "Sector Fund", "United States", "Equity ETF", 0.06, 0.18),
    _s("SMH", "VanEck Semiconductor ETF", "Technology", "Sector Fund", "United States", "Equity ETF", 0.22, 0.34),

    # --- Bonds, cash, commodities, crypto -----------------------------------
    _s("BND", "Vanguard Total Bond Market ETF", "Fixed Income", "Intermediate Core Bond", "United States", "Bond ETF", 0.03, 0.06),
    _s("AGG", "iShares Core US Aggregate Bond ETF", "Fixed Income", "Intermediate Core Bond", "United States", "Bond ETF", 0.03, 0.06),
    _s("TLT", "iShares 20+ Year Treasury Bond ETF", "Fixed Income", "Long Government", "United States", "Bond ETF", 0.02, 0.15),
    _s("SHY", "iShares 1-3 Year Treasury Bond ETF", "Fixed Income", "Short Government", "United States", "Bond ETF", 0.025, 0.02),
    _s("TIP", "iShares TIPS Bond ETF", "Fixed Income", "Inflation-Protected Bond", "United States", "Bond ETF", 0.03, 0.07),
    _s("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "Fixed Income", "Corporate Bond", "United States", "Bond ETF", 0.035, 0.08),
    _s("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "Fixed Income", "High Yield Bond", "United States", "Bond ETF", 0.05, 0.10),
    _s("BIL", "SPDR Bloomberg 1-3 Month T-Bill ETF", "Cash", "Ultrashort Bond", "United States", "Cash", 0.045, 0.005),
    _s("GLD", "SPDR Gold Shares", "Commodities", "Precious Metals", "Global", "Commodity", 0.07, 0.15),
    _s("IAU", "iShares Gold Trust", "Commodities", "Precious Metals", "Global", "Commodity", 0.07, 0.15),
    _s("SLV", "iShares Silver Trust", "Commodities", "Precious Metals", "Global", "Commodity", 0.05, 0.28),
    _s("DBC", "Invesco DB Commodity Index Fund", "Commodities", "Broad Commodity", "Global", "Commodity", 0.04, 0.18),
    _s("VNQ", "Vanguard Real Estate ETF", "Real Estate", "REIT Fund", "United States", "Equity ETF", 0.06, 0.22),
    _s("BTC-USD", "Bitcoin USD", "Digital Assets", "Cryptocurrency", "Global", "Crypto", 0.35, 0.65),
    _s("ETH-USD", "Ethereum USD", "Digital Assets", "Cryptocurrency", "Global", "Crypto", 0.30, 0.75),
    _s("IBIT", "iShares Bitcoin Trust", "Digital Assets", "Cryptocurrency", "United States", "Crypto", 0.35, 0.63),
]

REFERENCE: dict[str, ReferenceSecurity] = {s.ticker: s for s in _UNIVERSE}

# Sector weights of the S&P 500, used to flag over/under-exposure versus a
# broad-market benchmark. Approximate and static -- indicative, not precise.
BENCHMARK_SECTOR_WEIGHTS: dict[str, float] = {
    "Technology": 0.32,
    "Financial Services": 0.13,
    "Healthcare": 0.11,
    "Consumer Cyclical": 0.10,
    "Communication Services": 0.09,
    "Industrials": 0.08,
    "Consumer Defensive": 0.06,
    "Energy": 0.04,
    "Utilities": 0.025,
    "Real Estate": 0.02,
    "Basic Materials": 0.02,
}

# Asset classes that behave like a defensive ballast in a drawdown.
DEFENSIVE_ASSET_CLASSES = {"Bond ETF", "Cash", "Commodity"}


def lookup(ticker: str) -> ReferenceSecurity | None:
    return REFERENCE.get(ticker.strip().upper())


def search(query: str, limit: int = 12) -> list[ReferenceSecurity]:
    """Rank reference securities against a free-text query.

    Exact ticker matches rank first, then ticker prefixes, then name substrings.
    """
    q = query.strip().upper()
    if not q:
        return []

    scored: list[tuple[int, ReferenceSecurity]] = []
    for sec in _UNIVERSE:
        name = sec.name.upper()
        if sec.ticker == q:
            score = 0
        elif sec.ticker.startswith(q):
            score = 1
        elif name.startswith(q):
            score = 2
        elif q in sec.ticker:
            score = 3
        elif q in name:
            score = 4
        else:
            continue
        scored.append((score, sec))

    scored.sort(key=lambda pair: (pair[0], pair[1].ticker))
    return [sec for _, sec in scored[:limit]]
