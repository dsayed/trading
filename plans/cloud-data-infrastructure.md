# Trading Platform — Cloud Data Infrastructure Plan

## Problem Statement

The current project runs locally on SQLite with no historical data persistence, no cloud
deployment, and no multi-user API access. To support backtesting, signal fusion, and
unattended data collection across stocks, options, forex, and macro data — we need a
cloud-hosted data layer that stores raw data permanently and serves it via an authenticated API.

---

## Key Decisions (Resolved)

| Question | Decision | Rationale |
|---|---|---|
| Cloud DB | **Supabase** (PostgreSQL) | Free 500MB → $25/mo for 8GB. Built-in dashboard, REST API, SQL |
| Backend hosting | **Railway** | Free $5/mo credit covers light workloads. Simple git-push deploy |
| Frontend hosting | **Vercel** | Already the natural fit for the React dashboard. Free tier. |
| Data collection scheduler | **GitHub Actions** | Free 2000 min/mo. Cron syntax. Secrets management for API keys. |
| Multi-user access | **API key auth** (static keys, hashed in DB) | Simpler than OAuth for a small team. Each user gets a key. |
| Raw vs fused data | **Always keep raw** | Store exactly as received. Views/materialized tables for fusion later. No irreversible transforms. |
| Universe size | **Historical S&P500 constituents first**, then expand | Start manageable (~600 unique symbols), add Russell 2000 / all-US later |
| Historical S&P500 members | **GitHub repo (fja05680/sp500)** | CSV with every addition/removal since ~1996 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS (cron — unattended, free)               │
│  ├── collect_fred.yml         (weekly)                  │
│  ├── collect_equity_bars.yml  (daily, after close)      │
│  ├── collect_options.yml      (daily)                   │
│  ├── collect_cot.yml          (weekly, Friday)          │
│  └── collect_economic_cal.yml (weekly)                  │
└─────────────────────┬───────────────────────────────────┘
                      │ writes
┌─────────────────────▼───────────────────────────────────┐
│  SUPABASE POSTGRESQL (cloud DB)                         │
│  Raw tables — immutable, source-attributed              │
│  equity_bars, forex_bars, macro_series,                 │
│  options_snapshots, index_constituents,                 │
│  earnings_calendar, economic_calendar, cot_report       │
└─────────────────────┬───────────────────────────────────┘
                      │ reads
┌─────────────────────▼───────────────────────────────────┐
│  FASTAPI on RAILWAY                                     │
│  API key auth middleware                                │
│  Existing signal engine (reads from Supabase)           │
│  New: /data/* endpoints for raw data access             │
│  New: /backtest/* endpoints (Phase 3)                   │
└─────────────────────┬───────────────────────────────────┘
                      │ queries
┌─────────────────────▼───────────────────────────────────┐
│  VERCEL — React Dashboard                               │
│  Existing dashboard + new data explorer views           │
└─────────────────────────────────────────────────────────┘
```

---

## Database Schema (Raw — Never Delete)

```sql
-- Instrument universe
CREATE TABLE instruments (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    exchange        TEXT,
    asset_class     TEXT,  -- 'equity', 'etf', 'forex', 'futures'
    sector          TEXT,
    industry        TEXT,
    market_cap      REAL,
    last_updated    DATE
);

-- Historical index membership (S&P500, NDX, RUT, etc.)
CREATE TABLE index_constituents (
    index_name      TEXT,   -- 'SP500', 'NDX100', 'RUT2000'
    symbol          TEXT,
    date_added      DATE,
    date_removed    DATE,   -- NULL = currently in index
    PRIMARY KEY (index_name, symbol, date_added)
);

-- Equity daily bars (raw, source-attributed)
CREATE TABLE equity_bars (
    symbol          TEXT,
    date            DATE,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          BIGINT,
    interval        TEXT DEFAULT '1d',
    source          TEXT,   -- 'yahoo', 'polygon', 'fmp'
    PRIMARY KEY (symbol, date, interval)
);

-- Forex bars
CREATE TABLE forex_bars (
    pair            TEXT,   -- 'EUR/USD'
    date            DATE,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    interval        TEXT DEFAULT '1d',
    source          TEXT,
    PRIMARY KEY (pair, date, interval)
);

-- Options chain snapshots (daily)
CREATE TABLE options_snapshots (
    symbol          TEXT,
    snapshot_date   DATE,
    expiry          DATE,
    strike          REAL,
    option_type     TEXT,   -- 'call' | 'put'
    bid             REAL,
    ask             REAL,
    last            REAL,
    volume          INT,
    open_interest   INT,
    iv              REAL,
    delta           REAL,
    gamma           REAL,
    theta           REAL,
    vega            REAL,
    source          TEXT,
    PRIMARY KEY (symbol, snapshot_date, expiry, strike, option_type)
);

-- FRED macro series (raw observations)
CREATE TABLE macro_series (
    series_id       TEXT,   -- 'VIXCLS', 'DFF', 'T10Y2Y', etc.
    date            DATE,
    value           REAL,
    PRIMARY KEY (series_id, date)
);

CREATE TABLE macro_series_meta (
    series_id       TEXT PRIMARY KEY,
    name            TEXT,
    description     TEXT,
    frequency       TEXT,   -- 'daily', 'weekly', 'monthly', 'quarterly'
    category        TEXT,   -- 'rates', 'inflation', 'labor', 'volatility'
    last_synced     TIMESTAMPTZ
);

-- Earnings calendar
CREATE TABLE earnings_calendar (
    symbol          TEXT,
    report_date     DATE,
    timing          TEXT,   -- 'BMO' (before market open) | 'AMC' (after market close)
    eps_estimate    REAL,
    eps_actual      REAL,
    revenue_estimate REAL,
    revenue_actual  REAL,
    source          TEXT,
    PRIMARY KEY (symbol, report_date)
);

-- Economic events (NFP, CPI, FOMC, etc.)
CREATE TABLE economic_calendar (
    id              TEXT PRIMARY KEY,
    event           TEXT,
    country         TEXT,
    event_date      TIMESTAMPTZ,
    actual          REAL,
    estimate        REAL,
    previous        REAL,
    impact          TEXT,   -- 'high' | 'medium' | 'low'
    source          TEXT
);

-- CFTC Commitment of Traders (weekly)
CREATE TABLE cot_report (
    report_date                 DATE,
    commodity                   TEXT,
    commercials_long            BIGINT,
    commercials_short           BIGINT,
    large_speculators_long      BIGINT,
    large_speculators_short     BIGINT,
    small_speculators_long      BIGINT,
    small_speculators_short     BIGINT,
    PRIMARY KEY (report_date, commodity)
);

-- API key management (multi-user)
CREATE TABLE api_keys (
    key_hash        TEXT PRIMARY KEY,   -- SHA-256 of actual key
    name            TEXT,               -- e.g. "david-laptop"
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_used       TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    rate_limit_per_hour INT DEFAULT 1000
);
```

---

## FRED Series to Collect

```toml
[fred.series]
# Volatility / Market Stress
VIXCLS       = "CBOE Volatility Index (VIX)"
BAMLH0A0HYM2 = "High Yield Credit Spread"
TEDRATE      = "TED Spread (3-month LIBOR minus T-bill)"

# Rates
DFF          = "Fed Funds Rate (daily)"
DGS2         = "2-Year Treasury Yield"
DGS10        = "10-Year Treasury Yield"
DGS30        = "30-Year Treasury Yield"
T10Y2Y       = "10Y-2Y Yield Curve Spread"
T10Y3M       = "10Y-3M Yield Curve Spread"

# Inflation
CPIAUCSL     = "CPI All Urban Consumers (monthly)"
PCEPI        = "PCE Price Index"
T5YIE        = "5-Year Breakeven Inflation"
T10YIE       = "10-Year Breakeven Inflation"

# Labor
UNRATE       = "Unemployment Rate"
ICSA         = "Initial Jobless Claims (weekly)"
JTSJOL       = "JOLTS Job Openings"
CIVPART      = "Labor Force Participation Rate"

# Growth / Activity
A191RL1Q225SBEA = "Real GDP Growth Rate (quarterly)"
RSXFS        = "Retail Sales ex Food Service"
INDPRO       = "Industrial Production Index"
NAPM         = "ISM Manufacturing PMI"

# Dollar / FX
DTWEXBGS     = "Dollar Index (broad, goods & services)"
DTWEXAFEGS   = "Dollar Index (advanced foreign economies)"

# Money Supply
M2SL         = "M2 Money Stock"

# Consumer Sentiment
UMCSENT      = "University of Michigan Consumer Sentiment"
```

---

## Data Collection Schedule (GitHub Actions Cron)

| Workflow | Schedule | Data | Source |
|---|---|---|---|
| `collect_equity_bars` | Daily 8pm ET (Mon-Fri) | OHLCV for all tracked symbols | Yahoo |
| `collect_forex_bars` | Daily 6pm ET (Mon-Fri) | All major/minor pairs | TwelveData |
| `collect_fred` | Weekly Sunday | All FRED series | FRED API |
| `collect_cot` | Weekly Friday night | COT report | CFTC (free) |
| `collect_economic_cal` | Weekly Sunday | Upcoming events | FMP |
| `collect_earnings_cal` | Weekly Sunday | Upcoming earnings | FMP |
| `collect_options_snapshots` | Daily 6pm ET (Mon-Fri) | VIX term structure, put/call ratios | Yahoo + CBOE |
| `seed_historical` | One-time (manual trigger) | 20y bars for full universe | Yahoo |
| `seed_constituents` | One-time (manual trigger) | Historical S&P500 members | GitHub repo CSV |

---

## Universe Strategy

### Phase 1 (Start Here)
- Historical S&P500 constituents from `fja05680/sp500` GitHub repo (~600 unique symbols since 1996)
- All current Nasdaq 100 symbols
- Major ETFs: SPY, QQQ, IWM, GLD, SLV, USO, TLT, HYG, VXX, UVXY, major sector ETFs
- Major forex pairs: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD + crosses

### Phase 2 (Expand When Ready)
- Russell 2000 current + historical constituents
- All US stocks on NYSE/NASDAQ/AMEX (~8,000 symbols) — daily bars only, no options

### Key Principle
Store historical S&P500 membership in `index_constituents` so backtests don't suffer
**survivorship bias** — i.e., only testing against stocks that survived to today.

---

## Raw Data Principle

> **Never transform. Never delete. Always attribute.**

- Every row stores `source` (which API it came from)
- Corrections are new rows with a `corrected` flag, not overwrites
- Fusion/derived tables are **views** or separate `_derived` tables
- Raw tables are append-only

---

## Phase Plan

### Phase 1 — Infrastructure (Foundation)
1. Create Supabase project, apply schema
2. Set up Railway deployment for FastAPI backend
3. Add API key auth middleware to existing FastAPI app
4. Set up Vercel for dashboard
5. Configure GitHub repo secrets (all API keys)

### Phase 2 — Historical Seed (One-Time)
6. Build `seed_constituents` script (parse GitHub CSV → `index_constituents`)
7. Build `seed_equity_bars` script (Yahoo → 20y bars for all Phase 1 symbols)
8. Build `seed_fred` script (FRED → all macro series full history)
9. Build `seed_forex_bars` script (TwelveData → 10y forex history)
10. Run all seeds (triggered manually via GitHub Actions workflow_dispatch)

### Phase 3 — Live Collection (Ongoing)
11. Build `collect_equity_bars` GitHub Action (daily cron)
12. Build `collect_fred` GitHub Action (weekly cron)
13. Build `collect_cot` GitHub Action (weekly cron)
14. Build `collect_economic_calendar` GitHub Action (weekly cron)
15. Build `collect_forex_bars` GitHub Action (daily cron)

### Phase 4 — Adapt Existing Project
16. Add Supabase connection option to existing `core/database.py`
17. Add `MacroDataProvider` (reads from `macro_series` table)
18. Wire macro context into `IntermarketStrategy`
19. Build backtest engine reading from historical bars table

---

## Free Tier Coverage Analysis

### What We Already Have (All Free)

| Provider | What's Free | History Available | Use For |
|---|---|---|---|
| **Yahoo Finance** | No key needed | 20+ years daily bars | Equity bars, forex bars (EURUSD=X), options scanning |
| **FRED API** | Completely free, no key | Full history (50+ years) | All macro series |
| **CFTC** | Free download | Back to 1986 | COT weekly reports |
| **FMP** (free tier) | 300 calls/min | Varies | Earnings/economic calendar, sector lists |
| **Polygon** (free tier) | 5 calls/min | Delayed/limited | Universe listings, current prices |
| **TwelveData** (free tier) | 8 calls/min | Limited | Backup for bars, intraday |
| **MarketData** (free tier) | 100 calls/min | Current only | Options chains with Greeks for watchlist |

**Key insight: Yahoo Finance alone covers 20+ years of equity AND forex daily bars for free.**
Yahoo uses `EURUSD=X`, `GBPUSD=X` notation for forex — the same `fetch_bars()` call, zero extra cost.

---

### Phase 1 Data Collection — 100% Free

| Data | Source | Cost |
|---|---|---|
| 20y equity bars (S&P500 historical + ETFs) | Yahoo Finance | **Free** |
| 20y forex bars (major/minor pairs) | Yahoo Finance (EURUSD=X) | **Free** |
| Full FRED macro history | FRED API | **Free** |
| COT history since 1986 | CFTC download | **Free** |
| Earnings calendar | FMP free tier | **Free** |
| Economic calendar | FMP free tier | **Free** |
| Historical S&P500 constituents | GitHub CSV | **Free** |
| **Phase 1 total** | | **$0** |

---

### What Costs Money (and When)

| Need | Cost | When | Strategy |
|---|---|---|---|
| Historical options chains for backtesting | OptionsDX ~$30/mo | Phase 2 only | Subscribe 1 month, bulk download, cancel |
| Intraday bars (1m, 5m, 15m) | Polygon Starter $29/mo | Phase 2 only | Subscribe 1 month, seed history, cancel |
| Better options Greeks at scale | MarketData $12/mo | When watchlist > ~50 symbols | Ongoing — worth it |
| Supabase storage beyond 500MB | Supabase $25/mo | When DB exceeds 500MB | Upgrade when needed |

**Temporary subscription playbook**: Subscribe for 1 month, run the seed script to bulk-download years of history, cancel. Then use free tier for daily incremental updates. This is sound — daily updates need only the latest ~1 day of data, well within any free tier.

---

### Storage Estimate (Supabase Free Tier = 500MB)

| Data | Rows | Estimated Size |
|---|---|---|
| equity_bars (600 symbols × 20y × 252d) | ~3M | ~150MB |
| forex_bars (28 pairs × 20y × 252d) | ~141K | ~7MB |
| macro_series (25 series × 50y × varies) | ~200K | ~10MB |
| index_constituents | ~2K | negligible |
| earnings/economic calendar | ~50K | ~5MB |
| **Total Phase 1** | | **~175MB — within free tier** |

Phase 1 fits comfortably in Supabase's free 500MB tier. Expanding to Russell 2000 + all US stocks would push to ~1–2GB (upgrade to $25/mo at that point).

---

## Cost Estimate

| Service | Phase 1 | Phase 2+ |
|---|---|---|
| Supabase | Free (500MB) | $25/mo when >500MB |
| Railway | Free ($5 credit) | ~$5-10/mo |
| Vercel | Free | Free |
| GitHub Actions | Free | Free |
| All data sources | Free | Free (ongoing updates) |
| Historical options seed | — | $30 one-time |
| **Total** | **$0/mo** | **~$30-35/mo ongoing, $30 one-time for options** |
