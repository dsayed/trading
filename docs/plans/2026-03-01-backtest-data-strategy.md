# Backtest Data Strategy

*Discussed 2026-03-01. Not yet implemented.*

## Goal

Build a comprehensive financial data service — a separate project from the trading
system — that collects, stores, and serves historical market data. It should:

1. Support backtesting all current and future trading strategies
2. Run as a standalone service (local or cloud-hosted)
3. Collect data automatically on a schedule
4. Be usable by multiple consumers (trading system, notebooks, other projects)
5. Be extensible — add new data types without rebuilding existing tables

## Why a Separate Project?

The trading system is a consumer of market data, not a producer. Separating the data
layer creates clean boundaries:

- **Independent lifecycle** — data collection runs 24/7, trading system is used on-demand
- **Reusable** — Jupyter notebooks, other tools, even other people can use the same data
- **Deployable anywhere** — local SQLite for solo use, cloud-hosted API for sharing
- **Single responsibility** — the trading system focuses on signals/strategies, not ETL

The trading system connects to the data service either as:
- A local import (`from marketdata import BarStore`) when co-located
- An HTTP client (`GET /api/bars/AAPL?start=2020-01-01`) when remote

---

## Data Scope: Beyond OHLCV

Daily OHLCV bars support the current 5 strategies but lock out future experiments.
The bulk load should grab everything useful while we have API access.

### What Strategies Need What Data

| Data Type                  | Strategies It Unlocks                          | Source       | Cost        |
|----------------------------|------------------------------------------------|--------------|-------------|
| Daily OHLCV                | Momentum, Mean Reversion, MACD, Income         | FMP/Yahoo    | $59 one-time|
| Dividends & Splits         | Dividend strategies, total return backtesting   | FMP/Yahoo    | Included    |
| Quarterly Financials       | Value/fundamental, earnings quality             | FMP Premium  | Included    |
| Earnings Dates + Surprise  | Earnings momentum, event avoidance              | FMP Premium  | Included    |
| FRED Macro Series          | Intermarket/macro, regime detection             | FRED API     | Free forever|
| Sector/Industry            | Sector rotation, relative value                 | Yahoo `info` | Free        |
| Analyst Ratings            | Sentiment, contrarian signals                   | Yahoo        | Free        |
| Insider Transactions       | Insider following strategies                    | Yahoo/SEC    | Free        |
| Historical Options Chains  | Options backtesting, vol surface                | CBOE/Polygon | Expensive — skip for now |

### Bulk Load Plan ($59, ~16 minutes)

During the one-month FMP Premium subscription, grab everything per symbol:

| Endpoint                   | API Calls | Time at 750/min | Rows    | Size   |
|----------------------------|-----------|-----------------|---------|--------|
| Historical daily bars (30yr)| 1,900    | 3 min           | ~9.5M   | ~600MB |
| Quarterly income statements | 1,900    | 3 min           | ~20K    | ~10MB  |
| Quarterly balance sheets    | 1,900    | 3 min           | ~20K    | ~10MB  |
| Quarterly cash flow         | 1,900    | 3 min           | ~20K    | ~5MB   |
| Historical dividends        | 1,900    | 3 min           | ~50K    | ~3MB   |
| Earnings history            | 1,900    | 3 min           | ~20K    | ~3MB   |
| **Total**                  | **11,400**| **~16 minutes** |         | **~630MB** |

Plus free sources (no time pressure):

| Source                | Data                              | Time       |
|-----------------------|-----------------------------------|------------|
| FRED API (free key)   | ~30 macro series x 20yr           | 15 seconds |
| fja05680/sp500 GitHub | S&P membership 1996-present       | Instant    |
| Yahoo (free)          | Sector/industry per symbol        | ~30 min    |

### "Collect Going Forward" Data

Some data only exists as current snapshots — no free historical archive. Start
collecting daily and it becomes valuable over time:

| Data                    | Source              | Why No History Exists          |
|-------------------------|---------------------|--------------------------------|
| Implied volatility (ATM)| Yahoo options chain | Only shows current chain       |
| EPS estimate revisions  | Yahoo `eps_revisions`| Only shows current consensus  |
| Institutional holdings  | Yahoo `institutional_holders` | Only shows latest 13F |

After 1 year of daily IV snapshots → IV rank/percentile possible.
After 2 years → can backtest vol strategies.

---

## Why 15-20 Years Minimum

5 years (2021-2026) only covers one cycle in a historically unusual period (zero rates,
rapid hikes, AI rally). To meaningfully validate strategies you need 2-3 full market
cycles including at least one genuine crisis:

- 2008 financial crisis (stress-tests risk management, mean reversion failures)
- 2015-2016 commodity crash / China slowdown
- 2018 Q4 volatility spike
- 2020 COVID crash (momentum crashes, vol spikes)
- 2022 rate-hike bear market

| Strategy         | Why Long History Matters                                    |
|------------------|-------------------------------------------------------------|
| Momentum         | Momentum crashes are brutal — need 2008 to test survival    |
| Mean Reversion   | Need "it never reverts" scenarios (2008, prolonged bears)   |
| MACD Divergence  | Divergences are regime-dependent                            |
| Income (vol)     | Vol spikes like 2008/2020 are where premium selling blows up|
| Intermarket      | Macro regimes shift over decades                            |
| Fundamental      | Need to see value traps, quality factors through recessions |
| Earnings         | Earnings momentum works differently in bull vs bear markets |

## Strategy Warmup Requirements

Each strategy needs a warmup period before it can emit its first signal:

| Strategy       | Key Indicators               | Warmup Bars | ~Calendar Days |
|----------------|-------------------------------|-------------|----------------|
| Momentum       | SMA(50)                       | 50          | ~2.5 months    |
| Mean Reversion | RSI(14) + Bollinger(20)       | 25          | ~5 weeks       |
| Income         | ATR(14) + RSI(14) + SMA(50)   | 65          | ~3 months      |
| MACD Divergence| MACD(12/26/9)                 | 55          | ~2.5 months    |
| Intermarket    | SMA(20) + 4 benchmarks        | 25          | ~5 weeks       |

Total data needed per symbol = warmup (65 bars worst case) + backtest window.

---

## Survivorship Bias

The current S&P 500 list only contains today's winners. Backtesting with it ignores
companies that were in the index but failed (Lehman Brothers, Bear Stearns, Enron, etc.).

**Solution:** The [fja05680/sp500](https://github.com/fja05680/sp500) GitHub repo has
point-in-time S&P 500 membership from 1996 to present (updated Jan 2026). It tracks
every addition and removal with exact dates, sourced from Wikipedia. ~2,595 daily
snapshots covering ~1,500 unique tickers.

## Look-Ahead Bias

Financial statements have two dates: the period end (e.g., "Q4 2023 ending Dec 31")
and the filing date (e.g., "filed Feb 15, 2024"). If the backtester uses the period-end
date, it's "knowing" Q4 earnings 6 weeks early. Same applies to macro data (GDP
released a month after the quarter ends).

The schema tracks both dates. The backtester must query by filing/release date only.

---

## Provider Comparison for Bulk Load

### Free Tier — The Slow Road

| Provider          | Daily Limit     | History  | Calls Needed | Time to Complete |
|-------------------|-----------------|----------|--------------|------------------|
| Yahoo (yf batch)  | ~2K/hr, batches | 20+ yrs  | ~19 batches  | **~3 minutes**   |
| FMP Free          | 250 calls/day   | 5 yrs    | 1,900 calls  | **8 days**       |
| Twelve Data Free  | 800 calls/day   | 30+ yrs  | 1,900 calls  | **3 days**       |

Yahoo is fast and free but fragile — it reverse-engineers an unofficial API with no
contract. Yahoo has been [tightening access](https://github.com/ranaroussi/yfinance/issues/2340).

### Paid — The Fast Road (one month then cancel)

| Provider        | Plan     | Cost   | Rate Limit | History   | Time for 1,900 symbols |
|-----------------|----------|--------|------------|-----------|------------------------|
| **FMP Premium** | Premium  | $59/mo | 750/min    | **30 yrs**| **3 minutes (bars only)**|
| FMP Starter     | Starter  | $22/mo | 300/min    | 5 yrs     | 7 minutes              |
| Polygon Starter | Starter  | $29/mo | 5/min      | 5 yrs     | 6.3 hours              |
| MarketData      | Starter  | $12/mo | 100/min    | 10+ yrs   | 19 minutes             |

### Recommendation

**FMP Premium for one month ($59).** 30 years of history, 750 calls/min, bars +
financials + earnings + dividends loaded in ~16 minutes. This is normal paid API
usage — the rate limit IS the protection, staying under it makes you a regular customer.

### Incremental Daily Updates (Forever Free)

| Provider          | Active Symbols | Calls Needed  | Time         | Cost |
|-------------------|---------------|---------------|--------------|------|
| Yahoo (batch)     | ~700 active   | ~7 batch calls| **10 seconds** | Free |
| FRED              | ~30 series    | ~30 calls     | **15 seconds** | Free |

Yahoo batch download for bars. FRED for macro updates. Both free, both tiny.

---

## Database Schema

Separate tables per data type. Shared `symbol` key. Add new tables without touching
existing ones.

```sql
-- ═══════════════════════════════════════════════
-- PRICE DATA
-- ═══════════════════════════════════════════════

CREATE TABLE bars (
    symbol  TEXT    NOT NULL,
    date    TEXT    NOT NULL,   -- ISO 8601 (YYYY-MM-DD)
    open    REAL   NOT NULL,
    high    REAL   NOT NULL,
    low     REAL   NOT NULL,
    close   REAL   NOT NULL,
    volume  INTEGER NOT NULL,
    source  TEXT,               -- 'yahoo', 'fmp', 'polygon'
    PRIMARY KEY (symbol, date)
);
CREATE INDEX idx_bars_date ON bars(date);

CREATE TABLE dividends (
    symbol   TEXT NOT NULL,
    ex_date  TEXT NOT NULL,
    amount   REAL NOT NULL,
    pay_date TEXT,
    source   TEXT,
    PRIMARY KEY (symbol, ex_date)
);

CREATE TABLE splits (
    symbol     TEXT NOT NULL,
    date       TEXT NOT NULL,
    ratio_from REAL NOT NULL,   -- e.g., 1
    ratio_to   REAL NOT NULL,   -- e.g., 4 (for a 4:1 split)
    source     TEXT,
    PRIMARY KEY (symbol, date)
);

-- ═══════════════════════════════════════════════
-- FUNDAMENTALS (point-in-time via filing_date)
-- ═══════════════════════════════════════════════

CREATE TABLE financial_statements (
    symbol       TEXT NOT NULL,
    period_end   TEXT NOT NULL,   -- fiscal quarter/year end
    filing_date  TEXT NOT NULL,   -- when SEC filing became public (avoid look-ahead)
    period_type  TEXT NOT NULL,   -- 'quarterly' or 'annual'
    -- Income statement
    revenue           REAL,
    gross_profit      REAL,
    operating_income  REAL,
    net_income        REAL,
    eps_basic         REAL,
    eps_diluted       REAL,
    ebitda            REAL,
    -- Balance sheet
    total_assets      REAL,
    total_liabilities REAL,
    shareholders_equity REAL,
    book_value_per_share REAL,
    cash_and_equivalents REAL,
    total_debt        REAL,
    -- Cash flow
    operating_cashflow REAL,
    capex             REAL,
    free_cashflow     REAL,
    dividends_paid    REAL,
    shares_outstanding REAL,
    source            TEXT,
    PRIMARY KEY (symbol, period_end, period_type)
);
CREATE INDEX idx_fin_filing ON financial_statements(symbol, filing_date);

CREATE TABLE earnings_history (
    symbol         TEXT NOT NULL,
    quarter_end    TEXT NOT NULL,
    report_date    TEXT NOT NULL,
    actual_eps     REAL,
    consensus_eps  REAL,
    surprise       REAL,
    surprise_pct   REAL,
    num_analysts   INTEGER,
    source         TEXT,
    PRIMARY KEY (symbol, quarter_end)
);

-- ═══════════════════════════════════════════════
-- MACRO & ECONOMIC (point-in-time via release_date)
-- ═══════════════════════════════════════════════

CREATE TABLE macro_series (
    series_id    TEXT NOT NULL,   -- FRED code, e.g., 'FEDFUNDS', 'DGS10'
    period_date  TEXT NOT NULL,   -- the period this data covers
    release_date TEXT NOT NULL,   -- when it became publicly available
    value        REAL NOT NULL,
    PRIMARY KEY (series_id, period_date)
);
CREATE INDEX idx_macro_release ON macro_series(series_id, release_date);

-- ═══════════════════════════════════════════════
-- CLASSIFICATIONS & MEMBERSHIP
-- ═══════════════════════════════════════════════

CREATE TABLE index_membership (
    index_name   TEXT NOT NULL,   -- 'sp500', 'nasdaq100', 'dow30'
    symbol       TEXT NOT NULL,
    added_date   TEXT NOT NULL,
    removed_date TEXT,            -- NULL = still a member
    PRIMARY KEY (index_name, symbol, added_date)
);

CREATE TABLE sector_membership (
    symbol         TEXT NOT NULL,
    sector         TEXT NOT NULL,   -- GICS sector
    industry       TEXT NOT NULL,   -- GICS industry
    effective_date TEXT NOT NULL,   -- when this classification took effect
    PRIMARY KEY (symbol, effective_date)
);

-- ═══════════════════════════════════════════════
-- SNAPSHOTS (collected daily, grows over time)
-- ═══════════════════════════════════════════════

CREATE TABLE implied_vol (
    symbol        TEXT NOT NULL,
    date          TEXT NOT NULL,
    iv_30d        REAL,          -- ATM 30-day implied vol
    hv_20d        REAL,          -- 20-day historical (realized) vol
    put_call_ratio REAL,
    source        TEXT,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE analyst_ratings (
    symbol       TEXT NOT NULL,
    date         TEXT NOT NULL,
    firm         TEXT,
    action       TEXT,           -- 'upgrade', 'downgrade', 'initiate', 'reiterate'
    rating       TEXT,           -- 'buy', 'hold', 'sell', etc.
    price_target REAL,
    source       TEXT
);
CREATE INDEX idx_ratings ON analyst_ratings(symbol, date);

CREATE TABLE insider_trades (
    symbol           TEXT NOT NULL,
    filing_date      TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    insider_name     TEXT,
    title            TEXT,
    transaction_type TEXT,        -- 'P' (purchase), 'S' (sale)
    shares           INTEGER,
    price            REAL,
    source           TEXT
);
CREATE INDEX idx_insider ON insider_trades(symbol, filing_date);

-- ═══════════════════════════════════════════════
-- METADATA
-- ═══════════════════════════════════════════════

CREATE TABLE data_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- e.g., ('last_updated', '2026-03-01')
--       ('bulk_load_source', 'fmp_premium')
--       ('bars_last_date', '2026-02-28')
--       ('macro_last_date', '2026-02-28')

CREATE TABLE symbols (
    symbol       TEXT PRIMARY KEY,
    name         TEXT,
    sector       TEXT,
    industry     TEXT,
    exchange     TEXT,
    asset_class  TEXT,            -- 'equity', 'etf', 'forex', 'index'
    first_bar    TEXT,            -- earliest bar date we have
    last_bar     TEXT,            -- latest bar date we have
    is_active    INTEGER DEFAULT 1
);
```

### Storage Estimates

| Table                  | Rows (1,900 symbols, 20yr) | Size     |
|------------------------|---------------------------|----------|
| bars                   | ~9.5M                     | ~600MB   |
| dividends              | ~50K                      | ~3MB     |
| splits                 | ~5K                       | <1MB     |
| financial_statements   | ~60K                      | ~25MB    |
| earnings_history       | ~20K                      | ~3MB     |
| macro_series           | ~50K                      | ~5MB     |
| index_membership       | ~5K                       | <1MB     |
| sector_membership      | ~5K                       | <1MB     |
| implied_vol            | grows ~500/day            | ~0 initially |
| symbols                | ~2K                       | <1MB     |
| **Total**              |                           | **~640MB** |

Well within SQLite's comfort zone (~1GB). The `symbols` table acts as a registry
of everything we track, making it easy to find gaps in coverage.

---

## Architecture: Separate Project

### Project Structure

```
marketdata/                        # Separate git repo
├── pyproject.toml                 # Python package, installable via pip/uv
├── src/
│   └── marketdata/
│       ├── __init__.py
│       ├── db.py                  # MarketDB class: schema, migrations, connections
│       ├── store.py               # Read API: get_bars(), get_financials(), etc.
│       ├── loaders/
│       │   ├── __init__.py
│       │   ├── fmp.py             # FMP bulk loader (bars, financials, earnings, dividends)
│       │   ├── yahoo.py           # Yahoo loader (bars, dividends, sector info)
│       │   ├── fred.py            # FRED loader (macro series)
│       │   └── membership.py      # S&P 500 membership from GitHub CSV
│       ├── snapshots/
│       │   ├── __init__.py
│       │   └── daily.py           # Daily snapshot collector (IV, ratings, insider)
│       ├── server.py              # Optional FastAPI server for remote access
│       └── cli.py                 # CLI: marketdata load, marketdata update, marketdata serve
├── tests/
├── data/                          # Default location for the SQLite file
│   └── .gitkeep
└── README.md
```

### Two Operating Modes

**Local mode** — for solo use, backtesting on your laptop:
```
pip install marketdata    # or: uv add ../marketdata (as local dep)

# Initial bulk load
marketdata load --provider fmp --api-key xxx --start 1996-01-01

# Daily update
marketdata update

# Use from Python
from marketdata import MarketDB
db = MarketDB("./data/market.db")
bars = db.get_bars("AAPL", "2020-01-01", "2025-12-31")
```

**Cloud mode** — for sharing, automated collection:
```
# Deploy as a service (Fly.io, Railway, VPS, etc.)
marketdata serve --port 8080

# Consumers connect via HTTP
GET /api/bars/AAPL?start=2020-01-01&end=2025-12-31
GET /api/financials/AAPL?type=quarterly
GET /api/macro/DGS10?start=2020-01-01
```

### How the Trading System Connects

The trading system's backtester would use a `MarketDataProvider` adapter:

```python
# In the trading system
from marketdata import MarketDB

class BacktestDataProvider:
    """DataProvider that reads from the local market database."""
    def __init__(self, db_path: str):
        self.db = MarketDB(db_path)

    def fetch_bars(self, instrument, start, end):
        return self.db.get_bars(instrument.symbol, start, end)
```

Or for remote access:

```python
class RemoteMarketDataProvider:
    """DataProvider that reads from a remote marketdata service."""
    def __init__(self, base_url: str):
        self.base_url = base_url

    def fetch_bars(self, instrument, start, end):
        resp = httpx.get(f"{self.base_url}/api/bars/{instrument.symbol}",
                         params={"start": str(start), "end": str(end)})
        return pd.DataFrame(resp.json())
```

---

## Cloud Hosting Options

### For Automated Data Collection (the scheduler)

The service needs to run a daily job: fetch new bars, snapshot IV, update macro data.

| Option | Cost | Pros | Cons |
|--------|------|------|------|
| **GitHub Actions cron** | Free (public repo) or 2K min/mo (private) | Zero infrastructure, runs daily, pushes to storage | No persistent server, output goes to artifact/S3 |
| **Fly.io** | ~$3-5/mo (shared CPU + 1GB volume) | Persistent SQLite on volume, cron via supercronic | No free tier anymore, volume snapshot charges |
| **Railway** | Free tier: $5 credit/mo | Easy deploy, persistent disk | Limited free compute |
| **Cheap VPS (Hetzner)** | ~$4/mo (CX22) | Full control, cron built-in, 20GB disk | Manual setup |
| **Home machine + cron** | Free | No cloud needed | Must be running, no remote access |

### For Serving Data to Remote Consumers

| Option | Cost | Latency | Notes |
|--------|------|---------|-------|
| **SQLite file on S3 + local download** | ~$0.01/mo | None after download | Best for backtesting (local speed). Consumer downloads ~640MB file periodically. |
| **Turso (SQLite edge)** | Free (5GB, 500M reads/mo) | ~5ms | Embedded replicas = local read speed. Free tier fits our data. Offline sync in beta. |
| **FastAPI on Fly.io/VPS** | $3-5/mo | ~50-100ms per query | Full API, auth, rate limiting. Slower for bulk queries. |
| **DuckDB on Motherduck** | Free (10GB) | ~20ms | Analytical queries, column-oriented. Overkill for our use case. |

### Recommended Setup

**Phase 1: Build locally** ← START HERE
- SQLite file on disk, Python package with CLI
- Bulk load via FMP, daily updates via Yahoo/FRED
- Trading system imports the package directly (`from marketdata import MarketDB`)
- No server, no auth, no cloud — just a library and a file
- Cost: $0 ongoing (after $59 bulk load)

**Phase 2: Add hosted API + auth** ← LATER
- FastAPI server mode (`marketdata serve`)
- Token-based auth (API keys per consumer, rate limiting)
- Deploy to a VPS ($4/mo) or Fly.io with persistent volume
- Automated daily collection via cron on the server
- Consumers hit the API: `GET /api/bars/AAPL?start=2020-01-01`
- Cost: $4-5/mo

**Phase 3: Scale if needed**
- Turso for edge replicas (consumers get local-speed reads)
- Multiple API keys with usage tracking
- Bulk download endpoint (export SQLite snapshot for offline use)
- Cost: $4-5/mo + Turso free tier

Phase 1 is the only one that matters now. Everything else is additive — the schema,
loaders, and data don't change when you add a server on top.

---

## Incremental Updates: Design

Every table supports incremental updates by design:

```python
# Bars: fetch only new dates
last_date = db.query("SELECT MAX(date) FROM bars WHERE symbol=?", symbol)
new_bars = yahoo.download(symbol, start=last_date + 1 day, end=today)
db.upsert(new_bars)  # INSERT OR REPLACE

# Financials: fetch only new filings
last_filing = db.query("SELECT MAX(filing_date) FROM financial_statements WHERE symbol=?", symbol)
new_filings = fmp.get_income_statement(symbol, from_date=last_filing)
db.upsert(new_filings)

# Macro: fetch only new observations
last_obs = db.query("SELECT MAX(period_date) FROM macro_series WHERE series_id=?", series_id)
new_obs = fred.get_series(series_id, start=last_obs)
db.upsert(new_obs)

# Snapshots (IV, ratings): always append today's data
today_iv = compute_iv_from_options_chain(symbol)
db.insert(implied_vol, symbol=symbol, date=today, iv_30d=today_iv)
```

The `symbols` table tracks `first_bar` and `last_bar` per symbol, making it trivial
to find gaps:

```sql
-- Symbols with stale data (not updated in 3+ days)
SELECT symbol, last_bar FROM symbols
WHERE is_active = 1 AND last_bar < date('now', '-3 days');

-- Symbols with no financial data
SELECT s.symbol FROM symbols s
LEFT JOIN financial_statements f ON s.symbol = f.symbol
WHERE f.symbol IS NULL AND s.asset_class = 'equity';
```

---

## FRED Macro Series to Collect

All free, 120 requests/min, most series go back to the 1960s+.

| Series ID        | Description                       | Frequency | Use Case                |
|------------------|-----------------------------------|-----------|-------------------------|
| FEDFUNDS         | Fed Funds Rate                    | Daily     | Rate regime             |
| DGS2             | 2-Year Treasury Yield             | Daily     | Yield curve             |
| DGS10            | 10-Year Treasury Yield            | Daily     | Risk-free rate          |
| DGS30            | 30-Year Treasury Yield            | Daily     | Long rates              |
| T10Y2Y           | 10Y-2Y Spread                     | Daily     | Recession signal        |
| T10Y3M           | 10Y-3M Spread                     | Daily     | Recession signal        |
| CPIAUCSL         | CPI All Urban Consumers           | Monthly   | Inflation               |
| CPILFESL         | Core CPI (ex food/energy)         | Monthly   | Underlying inflation    |
| T5YIE            | 5-Year Breakeven Inflation        | Daily     | Inflation expectations  |
| UNRATE           | Unemployment Rate                 | Monthly   | Economic health         |
| PAYEMS           | Nonfarm Payrolls                  | Monthly   | Employment growth       |
| ICSA             | Initial Jobless Claims            | Weekly    | Leading indicator       |
| GDP              | Nominal GDP                       | Quarterly | Economic growth         |
| GDPC1            | Real GDP                          | Quarterly | Real growth             |
| INDPRO           | Industrial Production             | Monthly   | Manufacturing           |
| UMCSENT          | Consumer Sentiment (U of M)       | Monthly   | Consumer confidence     |
| RSAFS            | Retail Sales                      | Monthly   | Consumer spending       |
| HOUST            | Housing Starts                    | Monthly   | Leading indicator       |
| VIXCLS           | CBOE VIX                          | Daily     | Market fear gauge       |
| BAMLH0A0HYM2     | High Yield OAS (credit spread)    | Daily     | Credit risk             |
| DTWEXBGS         | Trade-Weighted Dollar Index       | Daily     | USD strength            |
| DCOILWTICO       | WTI Crude Oil                     | Daily     | Oil prices              |
| GOLDAMGBD228NLBM | Gold Price (London Fix)           | Daily     | Gold prices             |
| M2SL             | M2 Money Supply                   | Monthly   | Liquidity               |
| WALCL            | Fed Balance Sheet                 | Weekly    | QE/QT tracking          |

~25 series. Total download: <1 minute. Covers interest rates, inflation, employment,
GDP, consumer, housing, volatility, credit, currencies, and commodities.

---

## Open Questions

- **Adjusted vs raw prices.** Yahoo `auto_adjust=True` gives split/dividend-adjusted
  prices but you can't reconstruct the original. FMP gives both. Recommendation:
  store adjusted close as the primary `close` column (what strategies use), plus a
  separate `splits` table for reference.

- **Intraday data.** 1-minute bars for 500 symbols x 20 years = billions of rows,
  terabytes of storage. Not needed for current strategies (all daily). Could add a
  separate `intraday_bars` table later if needed, partitioned by date. Would require
  a more expensive data subscription.

- **Historical options chains.** Backtesting options strategies (covered calls,
  protective puts) properly requires historical IV surfaces. This is expensive
  (~$100-500/mo from CBOE DataShop or similar). The daily IV snapshot approach
  builds this dataset for free but takes 1-2 years to become useful.

- **Structured notes.** A structured note payoff analyzer would read the underlying's
  bar data from this same database. No special table needed — the payoff function
  is applied in code against the bars. Could add an `instruments` or
  `structured_products` table later if we want to model specific notes.

- **Database format.** SQLite is the recommendation for simplicity and portability.
  If query performance becomes an issue at scale (unlikely under 1GB), DuckDB is
  a drop-in alternative optimized for analytical queries. Parquet files on S3 are
  another option for very large datasets.

- **Authentication for the API.** If cloud-hosted, the server needs API key auth
  to prevent abuse. Simple Bearer token is sufficient initially.

- **Data quality.** Need a validation step after bulk load: check for gaps (missing
  trading days), suspicious values (zero prices, extreme outliers), and symbol
  mismatches (ticker changes over time, e.g., FB → META).
