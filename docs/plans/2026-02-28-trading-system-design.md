# Trading System Design

**Date:** 2026-02-28
**Status:** Approved

## Overview

A hybrid trading system that generates automated signals from multiple strategy types, presents actionable playbooks with step-by-step broker instructions, and tracks portfolio performance with tax awareness. Execution is manual — the user sets limit/conditional orders at their broker (Fidelity) based on the system's recommendations.

## Key Requirements

| Dimension | Decision |
|---|---|
| **Type** | Hybrid — automated signals, manual execution |
| **Assets** | Asset-class agnostic (stocks, crypto, options, futures) |
| **Pipeline** | Research → backtest → paper trade → live signals |
| **Strategies** | Multi-approach (technical + fundamental + statistical) |
| **Data** | Pluggable sources, start free, user's broker is Fidelity |
| **Interface** | CLI for research/backtesting + web dashboard for daily monitoring |
| **Risk** | Core feature. Fixed stake ($10k). Tax-aware: favor long-term capital gains |
| **Tempo** | Swing/position — not HFT. Limit orders set ahead of time |
| **Multi-user** | Designed for it (user_id on every table), but auth/deployment deferred |

## Architecture: Plugin-Based Python Core + Web UI

A Python core library with a plugin architecture. Strategies, data sources, brokers, and risk managers are all plugins conforming to clean interfaces. A central in-process event bus connects them. CLI tools are built on the core. A FastAPI web API serves a React dashboard.

### Why This Approach

- Extensible without being over-engineered
- Adding a new data source or strategy means writing a plugin, not modifying core code
- Clean abstractions without microservice overhead
- The plugin interfaces *are* the architecture

### Tech Stack

- **Python 3.12+** with **uv** for dependency management
- **pandas / numpy** for data analysis
- **FastAPI** for the web API layer
- **PostgreSQL** for data storage (multi-user ready from day one)
- **React** for the dashboard
- **Pydantic** for data models and config validation

## Project Structure

```
trading/
├── core/                  # Core engine
│   ├── engine.py          # Orchestrator: wires plugins, runs pipeline
│   ├── bus.py             # In-process event bus
│   ├── models.py          # Pydantic models: Instrument, Signal, Order, Position, Trade
│   ├── portfolio.py       # Portfolio state: positions, P&L, cash, tax lots
│   └── config.py          # Configuration loading and validation
│
├── plugins/
│   ├── data/              # DATA PROVIDERS
│   │   ├── base.py        # DataProvider protocol
│   │   ├── yahoo.py       # Yahoo Finance (free, daily)
│   │   ├── alpaca.py      # Alpaca (free tier, paper trading)
│   │   └── fidelity.py    # Fidelity (when available)
│   │
│   ├── strategies/        # STRATEGIES — consume data, emit signals
│   │   ├── base.py        # Strategy protocol
│   │   ├── momentum.py    # Momentum / trend following
│   │   ├── mean_revert.py # Mean reversion
│   │   └── composite.py   # Combines multiple strategies
│   │
│   ├── risk/              # RISK MANAGERS — filter and size signals
│   │   ├── base.py        # RiskManager protocol
│   │   ├── fixed_stake.py # Fixed stake sizing
│   │   └── tax_aware.py   # Tax-lot tracking, penalizes short-term exits
│   │
│   └── brokers/           # BROKERS — order abstraction
│       ├── base.py        # Broker protocol
│       ├── paper.py       # Paper trading (simulated)
│       └── manual.py      # Manual mode: generates limit orders for user
│
├── backtest/              # Backtesting engine
│   ├── runner.py          # Runs strategy over historical data
│   ├── metrics.py         # Sharpe, drawdown, tax-adjusted return
│   └── report.py          # Generate backtest reports
│
├── optimizer/             # Growth engine
│   ├── allocator.py       # Capital allocation (fractional Kelly)
│   ├── scenarios.py       # What-if scenario modeling
│   └── projections.py     # Compounding growth projections
│
├── api/                   # FastAPI web API
│   └── ...
│
├── dashboard/             # React web dashboard
│   └── ...
│
└── cli/                   # CLI tools
    └── ...
```

## Core Data Models

```
Instrument       # What you're trading (ticker, asset class, exchange)
Bar              # OHLCV price data for a time period
Signal           # Direction, conviction (0-1), rationale text, source strategy
Order            # Sized order: instrument, quantity, limit price, type
Position         # Open position: instrument, quantity, avg cost, tax lots
TaxLot           # Individual purchase: date, quantity, cost basis
Trade            # Completed round-trip: entry → exit, realized P&L, holding period
Portfolio        # All positions, cash, total value, unrealized P&L
```

## Pipeline Flow

The system operates as a pipeline that runs on a schedule or on-demand:

1. **DATA FETCH** — DataProvider plugins fetch latest bars for watched instruments, normalized into standard Bar format regardless of source.

2. **SIGNAL GENERATION** — Strategy plugins consume bars and emit Signals. Each Signal has: instrument, direction (long/short/close), conviction (0-1), and a plain-English rationale. CompositeStrategy aggregates signals from multiple sub-strategies.

3. **RISK FILTERING** — RiskManager plugins filter and size signals:
   - `fixed_stake`: Position sizing based on the fixed stake amount
   - `tax_aware`: Checks holding periods, penalizes or defers short-term exits, suggests alternative lots

4. **ORDER PRESENTATION (Manual Mode)** — Orders are displayed as Action Playbooks with step-by-step broker instructions, risk framing, and tax implications.

5. **TRADE TRACKING** — User confirms execution. Portfolio updates, new tax lots created. Performance metrics recalculated.

### Scheduling

- **Daily cron** — run after market close, review signals next morning
- **On-demand** — `trading scan` from CLI whenever desired
- **Alert-based** — background watcher sends notifications when price crosses thresholds

## Explainability: Action Playbooks

Every signal produces an Action Playbook — step-by-step instructions the user can follow at their broker.

### Principles

- **Plain English** — no jargon. Every signal gets a summary sentence explaining what's happening and why in everyday language.
- **Step-by-step broker instructions** — especially for complex instruments (options collars, spreads). Exact fields to fill, exact values to enter, in the order Fidelity presents them.
- **Risk framing** — every playbook shows what could go wrong. Dollar amounts for 5%, 10%, 25% drops. Worst-case scenarios spelled out clearly.
- **Confidence calibration** — signals show their historical accuracy. "When this strategy says buy at this conviction level, it's been profitable X% of the time." Honest uncertainty when history is limited.
- **Visual aids** (dashboard) — signal strength gauges, annotated price charts, portfolio heatmaps, tax lot timelines, equity curves.
- **Tax transparency** — every sell recommendation shows dollar tax impact and whether deferring would save money.

## Growth Engine

The optimizer takes the user's stake and finds the best allocation across available signals.

### Growth Modes

- **Conservative** — maximize risk-adjusted return, smaller diversified positions, favor long-term holds. Target: 8-15% annually.
- **Balanced** — moderate concentration, mix of swing trades and longer holds. Target: 15-30% annually.
- **Aggressive** — concentrate capital in highest-conviction signals, larger positions, shorter holds. Target: 30%+ annually with higher drawdown risk.

### Features

- **Optimal allocation** — uses fractional Kelly Criterion to size positions based on win rate and avg win/loss ratio
- **Projected scenarios** — best case, expected case, worst case for next 30 days
- **Compounding projections** — if current performance repeats, where does the stake go in 3/6/12 months
- **What-if gaming** — interactive: "What if AAPL drops 8%?", "What if a new signal appears while fully allocated?"
- **Growth tracker** — persistent dashboard widget showing stake growth, win rate, high water mark, drawdown, tax drag

## Backtesting Engine

Replays historical data through the full pipeline using the same code paths as live mode.

### Key Features

- **No look-ahead bias** — only uses data available at the time of each decision
- **Same code as live** — strategies, risk managers, and pipeline are identical
- **Tax-adjusted returns** — backtests calculate after-tax returns, not just gross
- **Strategy comparison** — side-by-side performance table across strategies
- **Calibration check** — verifies that conviction scores predict outcomes at stated accuracy
- **Honest warnings** — flags when backtest conditions differ from live conditions

## Dashboard Pages

1. **Home / Overview** — growth tracker, portfolio risk panel, today's signals, alert feed
2. **Signals** — current signals with full playbooks, sorted by conviction
3. **Portfolio** — positions with real-time P&L, tax lot details, days-to-long-term countdown
4. **Growth Optimizer** — select mode, view allocation plan, run what-if scenarios
5. **Backtests** — run and compare backtests, view reports
6. **History** — complete decision log with rationale for every signal, risk decision, and trade

## CLI Commands

```
trading scan                 # Run pipeline, show today's signals
trading scan --explain AAPL  # Full rationale for a specific signal
trading optimize             # Run growth optimizer
trading whatif               # Interactive scenario gaming
trading backtest <strategy>  # Run backtest
trading compare <s1> <s2>    # Compare strategies
trading portfolio            # Show current positions + tax lots
trading alerts               # Manage price/signal alerts
trading history              # Decision log
```

## Deferred (Phase 2)

- Multi-user authentication (OAuth / email+password)
- Web deployment (VPS, Docker Compose)
- User isolation with PostgreSQL row-level security
- Encrypted per-user API key storage
- Optional social features: leaderboard, strategy sharing, shared signal feed
