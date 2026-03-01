# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added
- **MACD Divergence strategy** — detects price-vs-MACD divergences for reversal signals (bullish and bearish)
- **Intermarket / Global Macro strategy** — uses SPY, dollar (UUP), bonds (TLT), and gold (GLD) trends to determine macro regime and favor aligned stocks
- **Dow 30 universe** — scan the 30 blue-chip Dow Jones industrials
- **Small-Cap 100 universe** — 100 liquid small-cap stocks outside the S&P 500
- **GICS sector universes** — scan any of the 11 S&P 500 sectors individually (Technology, Healthcare, Financials, Consumer Discretionary, Communication Services, Industrials, Consumer Staples, Energy, Utilities, Real Estate, Materials)
- Data provider injection for strategies via `inspect.signature` — strategies can optionally receive `data_provider` without changing the Strategy protocol
- Scanner page universe dropdown reorganized into Indices, Sectors, Forex, Trending, and Custom groups

## [0.5.0] - 2026-02-22

### Added
- **Multi-provider data layer** with composite routing — mix providers per role (bars, options, discovery, forex)
- **CachingDataProvider** with TTL-based caching for bars, universes, and movers
- **CompositeDataProvider** routes calls to role-specific sub-providers
- Provider role overrides in Settings (Options Provider, Discovery Provider, Forex Provider)
- Diagnostics panel in Settings showing provider health, API key status, and capabilities

## [0.4.0] - 2026-02-15

### Added
- **Market Scanner** — discover opportunities across large universes (S&P 500, NASDAQ 100, Forex Majors)
- **Scanner page** with streaming progress, strategy selection, holding period presets, and conviction filtering
- **Polygon.io provider** — stocks, options, forex, and discovery support ($29/mo)
- **FMP provider** — Financial Modeling Prep with discovery support
- **Mean Reversion strategy** — RSI + Bollinger Bands for bounce-back trades
- **Income strategy** — screens for premium-selling candidates using ATR volatility proxy
- **CSV Import** — upload Fidelity or generic CSV positions with auto-detection and preview
- **DiscoveryProvider protocol** — universe listing and movers discovery
- Scanner CLI: `uv run trading discover --universe sp500`
- Add-to-watchlist from scanner results

## [0.3.0] - 2026-02-08

### Added
- **Web dashboard** — React + Vite + Tailwind CSS frontend served alongside API
- **Position tracking** — CRUD for positions with tax lot support
- **Play Advisor system** — 3 advisors (stock play, covered call, protective put) generate actionable plays
- **Plays page** — view recommended plays for each position with option contracts
- **Config page** — edit watchlist, strategies, risk parameters, and data provider from the dashboard
- **Scan History page** — view past scan results stored in SQLite
- FastAPI backend with SQLite persistence

## [0.2.0] - 2026-01-25

### Added
- **Momentum strategy** with SMA crossover, RSI, and volume confirmation
- **Yahoo Finance data provider** — free market data with rate limiting
- **Fixed stake risk manager** with position sizing and stop-loss
- **Manual broker** with Action Playbook generation — step-by-step broker instructions
- **Pipeline engine** orchestrating data → strategy → risk → broker
- **CLI** with `trading scan` command and rich terminal output
- Plugin protocol system (DataProvider, Strategy, RiskManager, Broker)
- TOML configuration with sensible defaults
- Event bus for pipeline communication

## [0.1.0] - 2026-01-18

### Added
- Project scaffolding with uv package manager
- Core data models (Instrument, Bar, Signal, Order, Position, TaxLot, Trade)
- Design document and Phase 1 implementation plan
