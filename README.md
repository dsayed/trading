# Trading

A hybrid trading system that generates automated signals and gives you step-by-step instructions to execute them manually through your broker (e.g. Fidelity).

**Philosophy:** The system does the analysis. You make the final call.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy and customize config
cp config.example.toml config.toml

# Scan your watchlist
uv run trading scan

# Get a detailed playbook for a specific stock
uv run trading scan --explain AAPL
```

## What It Does

1. **Fetches market data** from Yahoo Finance (120 days of history)
2. **Runs strategies** against each symbol in your watchlist
3. **Sizes positions** based on your stake and risk tolerance
4. **Generates Action Playbooks** — step-by-step broker instructions with risk scenarios

Example output for `--explain`:

```
╭─── LONG AAPL ───────────────────────────────────╮
│  ACTION PLAYBOOK: Buy AAPL                       │
│                                                   │
│  WHAT TO DO:                                      │
│    1. Open your broker -> Trade -> Stocks          │
│    2. Enter: Buy 18 shares of AAPL                │
│    3. Order type: Limit                            │
│    4. Limit price: $223.50                         │
│    5. Time in force: Good 'til Canceled (GTC)      │
│    6. Review and submit                            │
│                                                   │
│  WHAT COULD GO WRONG:                             │
│    - If AAPL drops 5%: you lose ~$201              │
│    - If AAPL drops 10%: you lose ~$402             │
│    - If AAPL drops 25%: you lose ~$1,006           │
│                                                   │
│  STOP-LOSS:                                       │
│    Set a stop-loss at $212.33 to cap downside      │
╰──── conviction: 62% | strategy: momentum ────────╯
```

## Configuration

Edit `config.toml`:

```toml
[trading]
stake = 10000              # Total capital to deploy
max_position_pct = 0.40    # Max 40% of stake in one position
stop_loss_pct = 0.05       # 5% stop-loss on every position
data_provider = "yahoo"
strategies = ["momentum"]
risk_manager = "fixed_stake"
broker = "manual"
watchlist = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]
```

| Setting | What it controls |
|---|---|
| `stake` | Total dollar amount you're willing to invest |
| `max_position_pct` | Maximum % of stake in any single position |
| `stop_loss_pct` | Automatic stop-loss distance from entry price |
| `watchlist` | Symbols to scan for signals |

## Architecture

The system is plugin-based. Each component follows a Python Protocol, so you can swap implementations without changing the rest of the pipeline.

```
Data Provider  →  Strategy  →  Risk Manager  →  Broker
(Yahoo Finance)   (Momentum)   (Fixed Stake)    (Manual Playbooks)
```

**Pipeline flow:**
1. **Data Provider** fetches OHLCV bars for each symbol
2. **Strategy** analyzes the data and emits signals with plain-English rationale
3. **Risk Manager** sizes the position and adds stop-loss, filtering out signals that don't meet criteria
4. **Broker** formats the order into step-by-step instructions

### Current Plugins

| Component | Plugin | Description |
|---|---|---|
| Data | `yahoo` | Free market data via Yahoo Finance |
| Strategy | `momentum` | SMA crossover + RSI + volume confirmation |
| Risk | `fixed_stake` | Position sizing as % of fixed stake with stop-loss |
| Broker | `manual` | Action Playbooks with step-by-step broker instructions |

### Momentum Strategy Details

The momentum strategy looks at three factors:

- **SMA Crossover:** Is the short-term average (10-day) above the long-term (50-day)?
- **RSI:** Is buying/selling pressure healthy (not overbought/oversold)?
- **Volume:** Is trading volume confirming the move?

Each factor contributes to a conviction score (0-100%). The strategy generates plain-English rationale explaining exactly why it's recommending the trade.

## Project Structure

```
src/trading/
├── cli/main.py                    # CLI entry point (Typer + Rich)
├── core/
│   ├── models.py                  # Pydantic data models
│   ├── config.py                  # TOML config loading
│   ├── engine.py                  # Pipeline orchestration
│   └── bus.py                     # Event bus (for future use)
├── plugins/
│   ├── data/yahoo.py              # Yahoo Finance provider
│   ├── strategies/momentum.py     # Momentum strategy
│   ├── risk/fixed_stake.py        # Position sizer
│   └── brokers/manual.py          # Action Playbook generator
├── backtest/                      # (Phase 2)
└── optimizer/                     # (Phase 2)
```

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests (fast, no network calls)
uv run pytest

# Run all tests including live market data
uv run pytest -m "not slow"   # skip slow tests (default)
uv run pytest                  # all tests including live API calls

# Run a specific test file
uv run pytest tests/plugins/strategies/test_momentum.py -v
```

## Roadmap

- [ ] Web dashboard (FastAPI + React)
- [ ] Backtesting engine with historical replay
- [ ] Growth optimizer ("take $10k and grow it")
- [ ] Additional strategies (mean reversion, fundamental screening)
- [ ] Tax-aware trade timing (favor long-term capital gains)
- [ ] Additional data providers (Fidelity, Alpaca)
- [ ] Paper trading mode
