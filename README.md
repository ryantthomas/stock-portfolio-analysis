# Portfolio Analysis

Enter your holdings as tickers and weights, and see what the portfolio actually
looks like: where the risk really sits, how much of the diversification is real,
and which positions are doing the same job as each other.

Built as three layers that can be used independently:

| Layer | What it is | Where |
|---|---|---|
| **Web app** | React + TypeScript UI for building and inspecting a portfolio | `web/` |
| **API** | FastAPI service: market data ingestion and the analytics engine | `api/` |
| **Warehouse** | DuckDB landing zone modelled by dbt into analytics marts | `dbt/portfolio/`, `data/` |

---

## Quick start

Requires **Python 3.10+** and **Node 20.19+** (or 22.12+, as Vite 8 needs).
Nothing else — no database to provision, no API keys.

```bash
git clone -b claude/stock-portfolio-webapp-focr1k \
    https://github.com/ryantthomas/stock-portfolio-analysis.git
cd stock-portfolio-analysis

make setup      # Python venv + npm install
make dev        # API on :8000, web on :5173
```

Open <http://localhost:5173>. The app loads a three-fund portfolio and analyzes
it immediately, so there is something to look at before you type anything.

With no market data provider installed the app runs on the built-in **demo**
provider, which generates simulated prices. It is fully functional and needs no
network or API keys, and the UI shows a banner whenever it is active so the
numbers are never mistakable for real market data.

### Entering a portfolio

The app opens with a three-fund portfolio already loaded and analyzed, so there
is something to react to before you type anything. From there: `+ Add` for a new
position, `×` to drop one, and a preset picker to start from a different shape.

Position sizes can be entered two ways, toggled at the top of the holdings panel:

- **Percent** — shares of the portfolio. A running total is shown, and
  `Scale to 100` rescales what you have entered proportionally.
- **Amount ($)** — what each position is worth. The running total becomes the
  portfolio's value, and each row shows the percentage it works out to.

Nothing has to add up to a particular number in either mode. Sizes are
normalized proportionally, so `50/30/20`, `0.5/0.3/0.2` and `$5,000/$3,000/$2,000`
all describe the same portfolio and produce an identical analysis. Switching
modes converts the numbers rather than reinterpreting them, so the split you are
looking at never changes underneath you.

### Getting real market data

```bash
.venv/bin/pip install -e 'api[yfinance]'   # free, no key, good enough for daily closes
.venv/bin/pip install -e 'api[openbb]'     # preferred: many vendors behind one interface
```

Restart the API and it picks the best available source automatically.

---

## How the pieces fit together

```
   React app  ──POST /api/portfolio/analyze──▶  FastAPI
                                                  │
                                    ┌─────────────┴─────────────┐
                                    ▼                           ▼
                            provider chain              analytics engine
                       openbb → yfinance → demo     (risk, correlation,
                                    │                 diversification)
                                    ▼                           │
                          DuckDB  raw.prices                    │
                                  raw.securities  ◀─────────────┘
                                  raw.portfolio_holdings
                                    │
                                    ▼
                                  dbt
                       staging → intermediate → marts
```

The API answers requests directly from the analytics engine, so the app never
waits on dbt. Everything it fetches is also landed in DuckDB, where dbt models
it into marts that anything — a notebook, a BI tool, a scheduled digest — can
query with plain SQL.

---

## Market data providers

Providers sit behind one small interface (`api/app/providers/base.py`), so
adding a source means implementing two methods.

| Provider | Install | Notes |
|---|---|---|
| **OpenBB** | `pip install -e 'api[openbb]'` | Preferred. Fronts FMP, Intrinio, Polygon, Tiingo and others; better data is a credential away, not a code change. |
| **yfinance** | `pip install -e 'api[yfinance]'` | Free, no key. Fine for daily closes on equities, ETFs and crypto. |
| **demo** | built in | Deterministic simulated prices, correlated through a shared market factor. Runs offline. |

With `provider: "auto"` the chain is tried in that order and falls through on
failure, so one unavailable vendor never produces an error page. Every response
reports which provider actually served it.

---

## What gets computed

### Risk and return
Annualized return and volatility, Sharpe, Sortino, max drawdown, beta and
Jensen's alpha against a benchmark, tracking error, historical VaR and CVaR at
95%, and the best/worst day.

### Diversification
A 0–100 score, reported alongside the five components it is built from so it is
explainable rather than opaque:

| Component | Weight | What it measures |
|---|---|---|
| Correlation | 30% | Whether the holdings actually move independently |
| Position breadth | 25% | Effective holdings (1 / Herfindahl index) |
| Sector spread | 20% | Concentration across sectors |
| Concentration | 15% | How dominant the single largest position is |
| Asset class breadth | 10% | Equity / bond / commodity / cash coverage |

Correlation carries the most weight on purpose: twenty tickers that all move
together are not a diversified portfolio, however many of them there are.

Alongside the score: **effective holdings**, the **diversification ratio**
(weighted-average asset volatility over realized portfolio volatility — 1.0
means combining the positions achieved nothing), and the full correlation
matrix.

### Risk contribution
Each position's share of *total portfolio risk*, computed from the covariance
matrix rather than from weight alone. This is where a 5% position turns out to
be 15% of the risk. The UI flags any holding whose risk share materially
exceeds its weight.

### Findings
Rule-based observations about the shape of the allocation — dominant positions,
sector concentration, tilts against the broad market, redundant highly
correlated pairs, missing defensive ballast, home bias, cash drag, deep
drawdowns, and risk-adjusted underperformance. Each names the metric that
triggered it.

These describe structure. They are not investment advice, and the thresholds
that produce them are plain constants at the top of
`api/app/analytics.py` — adjust them to taste.

---

## The dbt project

```bash
make seed       # analyze a few example portfolios into the warehouse
make dbt        # build every model
make dbt-docs   # browse the model documentation and lineage
```

**staging** — deduplicated prices, metadata with blanks normalized to
`Unknown`, holdings with weights renormalized to sum to 1.

**intermediate** — daily returns, per-security statistics, daily-rebalanced
portfolio returns, pairwise correlations, positions enriched with metadata.

**marts** — the tables worth querying:

| Mart | One row per | Useful for |
|---|---|---|
| `mart_portfolio_diversification` | portfolio | Concentration, correlation, volatility reduction |
| `mart_portfolio_risk` | portfolio | Annualized return, vol, Sharpe, Sortino, drawdown, VaR |
| `mart_portfolio_performance` | portfolio × day | Equity curve and drawdown path |
| `mart_portfolio_allocation` | portfolio × dimension × bucket | Weights by sector, asset class, country, industry, ticker |
| `mart_correlation_matrix` | portfolio × pair | Heatmap-ready, symmetric, banded |
| `mart_portfolio_opportunities` | finding | The rules, in SQL |
| `mart_security_performance` | security | Per-ticker reference table |

Annualization, compounding and Sharpe live in `macros/finance.sql` so the
warehouse and the API use identical conventions.

Example — rank saved portfolios by how much volatility their diversification
actually bought:

```sql
select
    d.portfolio_label,
    d.holdings_count,
    round(d.effective_holdings, 1)    as effective_holdings,
    round(d.avg_correlation, 2)       as avg_correlation,
    round(d.diversification_ratio, 2) as div_ratio,
    round(r.annual_volatility, 3)     as vol,
    round(r.sharpe_ratio, 2)          as sharpe
from marts.mart_portfolio_diversification d
join marts.mart_portfolio_risk r using (portfolio_id)
-- Every analysis saves a snapshot, so keep only the newest run per name.
qualify row_number() over (
    partition by d.portfolio_label order by d.created_at desc
) = 1
order by d.diversification_ratio desc;
```

Query it however you like — `duckdb data/warehouse.duckdb`, the `/api/warehouse/query`
endpoint, or any BI tool that speaks DuckDB.

---

## API

Interactive docs at <http://127.0.0.1:8000/docs>.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/portfolio/analyze` | Full analysis for a set of holdings |
| `GET`  | `/api/search?q=` | Ticker autocomplete |
| `GET`  | `/api/health` | Provider availability and warehouse stats |
| `POST` | `/api/warehouse/dbt` | Trigger a dbt build |
| `GET`  | `/api/warehouse/tables` | List warehouse tables |
| `POST` | `/api/warehouse/query` | Read-only SQL against the marts |

```bash
curl -X POST http://127.0.0.1:8000/api/portfolio/analyze \
  -H 'Content-Type: application/json' \
  -d '{
        "holdings": [
          {"ticker": "VTI",  "weight": 50},
          {"ticker": "VXUS", "weight": 30},
          {"ticker": "BND",  "weight": 20}
        ],
        "benchmark": "SPY",
        "lookback_days": 1095
      }'
```

Weights can be percentages, decimals or arbitrary ratios — they are normalized
proportionally, so only relative sizing matters.

---

## Deploying

The API serves the built React app itself, so a deployment is **one container
on one origin** — no separate static host, no CORS to configure, one thing to
monitor. Everything below builds the same `Dockerfile`.

```bash
docker compose up --build     # http://localhost:8000
```

**Render** — commit `render.yaml`, then *New → Blueprint* and point it at the
repo. **Fly.io** — `fly launch --no-deploy` once, then `fly deploy`. Both read
the config files in the repo root. Anything that runs a container works the
same way; the image reads `$PORT` if the host injects one.

### Before you expose it publicly

The image defaults to a safe posture, but it is worth knowing what each switch
does:

| Setting | Default in image | Why |
|---|---|---|
| `PORTFOLIO_ENABLE_WAREHOUSE_API` | `false` | `/api/warehouse/query` runs arbitrary SQL and `/api/warehouse/dbt` spawns a subprocess. Operator tools, not features. **Never enable on a public site.** |
| `PORTFOLIO_PERSIST_PORTFOLIOS` | `false` | Otherwise every visitor's portfolio is written to the warehouse, unbounded and with no per-user isolation. |
| `PORTFOLIO_RATE_LIMIT_PER_MINUTE` | `30` | `/analyze` does real work and calls upstream market-data APIs. `0` disables. |

Three limits to be aware of:

- **The rate limiter is per-process.** Running N replicas allows roughly N×
  the configured rate, and it keys off `X-Forwarded-For`, which clients can
  spoof. It stops accidental loops and casual abuse, not a determined attacker
  — put a real limiter in your proxy or CDN if you need one.
- **There are no user accounts.** Portfolios are not saved per person; the app
  keeps your holdings in `localStorage` in your own browser.
- **The warehouse is a cache, not a database of record.** Without a mounted
  volume it resets on redeploy, which costs nothing but a refetch. dbt is a
  local/operator workflow, not something the deployed container runs.

### Market data in production

The image installs the `yfinance` extra, so a deployed instance serves real
prices and the simulated-data banner disappears. For better data, add the
OpenBB extra and its credentials — the provider chain picks the best available
source with no code change.

---

## Configuration

Environment variables, all prefixed `PORTFOLIO_` (or a `.env` file):

| Variable | Default | Purpose |
|---|---|---|
| `PORTFOLIO_DUCKDB_PATH` | `data/warehouse.duckdb` | Warehouse location |
| `PORTFOLIO_PROVIDER` | `auto` | Default provider preference |
| `PORTFOLIO_RISK_FREE_RATE` | `0.042` | Annualized rate for Sharpe |
| `PORTFOLIO_TRADING_DAYS` | `252` | Annualization factor |
| `PORTFOLIO_CORS_ORIGINS` | `http://localhost:5173,…` | Allowed browser origins (unused when one origin serves both) |
| `PORTFOLIO_OPENBB_VENDOR` | `yfinance` | Vendor OpenBB routes to |
| `PORTFOLIO_STATIC_DIR` | `web/dist` | Built frontend to serve; API-only if absent |
| `PORTFOLIO_ENABLE_WAREHOUSE_API` | `false` | Operator-only SQL and dbt endpoints |
| `PORTFOLIO_PERSIST_PORTFOLIOS` | `true` | Save a snapshot of each analyzed portfolio |
| `PORTFOLIO_RATE_LIMIT_PER_MINUTE` | `30` | Per-IP limit on `/analyze`; `0` disables |

---

## Development

```bash
make test       # pytest (57) + vitest (31)
make lint       # frontend typecheck + ruff
make dbt-test   # dbt schema tests
make reset      # wipe the warehouse and start clean
```

`make help` lists every target.

### Dependencies

Python ranges in `api/pyproject.toml` are capped at the next major (or at 1.0
for 0.x projects, where a minor bump can break). Both ends are tested rather
than assumed — the suite passes on the lowest allowed versions (fastapi 0.110,
pydantic 2.6, numpy 1.26, pandas 2.1, duckdb 0.10) and on the current ceiling
(fastapi 0.141, pydantic 2.13, numpy 2.4, pandas 3.0, duckdb 1.5).

```bash
# Re-verify the floor after changing a bound
uv pip install --resolution lowest-direct -e 'api[dev]'
cd api && pytest tests -q
```

The frontend pins via `web/package-lock.json`; use `npm ci` for a reproducible
install. `npm audit` is clean — Vite 8 builds with rolldown/oxc and drops the
esbuild dependency that carried the previous dev-server advisory. Vite 8
requires Node `^20.19 || >=22.12`, declared in `web/package.json` under
`engines` so npm warns up front on an older runtime.

---

## Notes and limitations

- **Daily rebalancing is assumed.** Reported statistics describe the target
  allocation you entered, not a buy-and-hold drift from it. For long windows
  the difference is real.
- **Backward-looking.** Every figure is computed from realized history over the
  chosen window. Correlations in particular tend to rise in a crisis, which is
  exactly when diversification is being relied upon.
- **Long-only, no cash flows.** No shorts, leverage, contributions, withdrawals,
  taxes or transaction costs.
- **Benchmark sector weights are approximate** and static, so the over/under-
  exposure flags are indicative rather than precise.
- **Not investment advice.** This is an analysis tool. The findings describe the
  structure of an allocation; what to do about it is your call.
