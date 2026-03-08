-- ============================================================
-- Trading Data Infrastructure — Initial Schema
-- Raw data only. Append-only. Source-attributed. Never delete.
-- ============================================================

-- ------------------------------------
-- Instrument universe
-- ------------------------------------
CREATE TABLE IF NOT EXISTS instruments (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    exchange        TEXT,
    asset_class     TEXT,
    sector          TEXT,
    industry        TEXT,
    market_cap      REAL,
    last_updated    DATE
);

-- ------------------------------------
-- Historical index membership
-- Tracks every addition/removal to prevent survivorship bias in backtests
-- ------------------------------------
CREATE TABLE IF NOT EXISTS index_constituents (
    index_name      TEXT,
    symbol          TEXT,
    date_added      DATE NOT NULL,
    date_removed    DATE,
    PRIMARY KEY (index_name, symbol, date_added)
);

CREATE INDEX IF NOT EXISTS idx_constituents_symbol ON index_constituents (symbol);
CREATE INDEX IF NOT EXISTS idx_constituents_index_date ON index_constituents (index_name, date_added);

-- ------------------------------------
-- Equity OHLCV bars (daily + intraday)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS equity_bars (
    symbol          TEXT        NOT NULL,
    date            DATE        NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL        NOT NULL,
    volume          BIGINT,
    interval        TEXT        NOT NULL DEFAULT '1d',
    source          TEXT        NOT NULL,
    PRIMARY KEY (symbol, date, interval)
);

CREATE INDEX IF NOT EXISTS idx_equity_bars_symbol_date ON equity_bars (symbol, date DESC);

-- ------------------------------------
-- Forex OHLCV bars
-- pair format: 'EUR/USD', 'GBP/USD', etc.
-- ------------------------------------
CREATE TABLE IF NOT EXISTS forex_bars (
    pair            TEXT        NOT NULL,
    date            DATE        NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL        NOT NULL,
    interval        TEXT        NOT NULL DEFAULT '1d',
    source          TEXT        NOT NULL,
    PRIMARY KEY (pair, date, interval)
);

CREATE INDEX IF NOT EXISTS idx_forex_bars_pair_date ON forex_bars (pair, date DESC);

-- ------------------------------------
-- Options chain daily snapshots
-- ------------------------------------
CREATE TABLE IF NOT EXISTS options_snapshots (
    symbol          TEXT        NOT NULL,
    snapshot_date   DATE        NOT NULL,
    expiry          DATE        NOT NULL,
    strike          REAL        NOT NULL,
    option_type     TEXT        NOT NULL,
    bid             REAL,
    ask             REAL,
    last            REAL,
    volume          INTEGER,
    open_interest   INTEGER,
    iv              REAL,
    delta           REAL,
    gamma           REAL,
    theta           REAL,
    vega            REAL,
    source          TEXT        NOT NULL,
    PRIMARY KEY (symbol, snapshot_date, expiry, strike, option_type)
);

CREATE INDEX IF NOT EXISTS idx_options_symbol_date ON options_snapshots (symbol, snapshot_date DESC);

-- ------------------------------------
-- FRED macro series (raw observations)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS macro_series (
    series_id       TEXT        NOT NULL,
    date            DATE        NOT NULL,
    value           REAL,
    PRIMARY KEY (series_id, date)
);

CREATE INDEX IF NOT EXISTS idx_macro_series_id_date ON macro_series (series_id, date DESC);

CREATE TABLE IF NOT EXISTS macro_series_meta (
    series_id       TEXT        PRIMARY KEY,
    name            TEXT        NOT NULL,
    description     TEXT,
    frequency       TEXT,
    category        TEXT,
    units           TEXT,
    last_synced     TIMESTAMPTZ
);

-- ------------------------------------
-- Earnings calendar
-- ------------------------------------
CREATE TABLE IF NOT EXISTS earnings_calendar (
    symbol          TEXT        NOT NULL,
    report_date     DATE        NOT NULL,
    timing          TEXT,
    eps_estimate    REAL,
    eps_actual      REAL,
    revenue_estimate REAL,
    revenue_actual  REAL,
    source          TEXT        NOT NULL,
    PRIMARY KEY (symbol, report_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar (report_date);

-- ------------------------------------
-- Economic events calendar (NFP, CPI, FOMC, etc.)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS economic_calendar (
    id              TEXT        PRIMARY KEY,
    event           TEXT        NOT NULL,
    country         TEXT        NOT NULL,
    event_date      TIMESTAMPTZ NOT NULL,
    actual          REAL,
    estimate        REAL,
    previous        REAL,
    impact          TEXT,
    source          TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_econ_cal_date ON economic_calendar (event_date);
CREATE INDEX IF NOT EXISTS idx_econ_cal_country ON economic_calendar (country, event_date);

-- ------------------------------------
-- CFTC Commitment of Traders (weekly)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS cot_report (
    report_date                 DATE        NOT NULL,
    commodity                   TEXT        NOT NULL,
    commercials_long            BIGINT,
    commercials_short           BIGINT,
    large_speculators_long      BIGINT,
    large_speculators_short     BIGINT,
    small_speculators_long      BIGINT,
    small_speculators_short     BIGINT,
    PRIMARY KEY (report_date, commodity)
);

-- ------------------------------------
-- API keys for multi-user access
-- Store SHA-256 hash of actual key — never store plaintext
-- ------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash            TEXT        PRIMARY KEY,
    name                TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used           TIMESTAMPTZ,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    rate_limit_per_hour INTEGER     NOT NULL DEFAULT 1000
);

-- ------------------------------------
-- Signal log (persisted scan results)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS signal_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol          TEXT        NOT NULL,
    direction       TEXT        NOT NULL,
    conviction      REAL,
    strategy        TEXT        NOT NULL,
    rationale       TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    context         JSONB
);

CREATE INDEX IF NOT EXISTS idx_signal_log_symbol ON signal_log (symbol, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_log_generated ON signal_log (generated_at DESC);
