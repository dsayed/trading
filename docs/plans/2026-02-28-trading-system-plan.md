# Trading System — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimum viable pipeline: `trading scan` fetches market data, runs a momentum strategy, sizes positions with a fixed stake, and outputs an Action Playbook with step-by-step broker instructions and risk framing.

**Architecture:** Plugin-based Python core. Strategies, data providers, risk managers, and brokers are Python Protocols. An engine wires them together and runs the pipeline. CLI built with Typer.

**Tech Stack:** Python 3.12+, uv, Pydantic, pandas, numpy, yfinance, Typer, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/trading/__init__.py`
- Create: `src/trading/core/__init__.py`
- Create: `src/trading/plugins/__init__.py`
- Create: `src/trading/plugins/data/__init__.py`
- Create: `src/trading/plugins/strategies/__init__.py`
- Create: `src/trading/plugins/risk/__init__.py`
- Create: `src/trading/plugins/brokers/__init__.py`
- Create: `src/trading/backtest/__init__.py`
- Create: `src/trading/optimizer/__init__.py`
- Create: `src/trading/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/plugins/__init__.py`
- Create: `tests/plugins/data/__init__.py`
- Create: `tests/plugins/strategies/__init__.py`
- Create: `tests/plugins/risk/__init__.py`
- Create: `tests/plugins/brokers/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "trading"
version = "0.1.0"
description = "Hybrid trading system with automated signals and manual execution"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pandas>=2.0",
    "numpy>=1.26",
    "yfinance>=0.2",
    "typer>=0.12",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
trading = "trading.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/trading"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: Create all __init__.py files**

Create every `__init__.py` listed above as empty files. Create the full directory tree:
```
src/trading/core/
src/trading/plugins/data/
src/trading/plugins/strategies/
src/trading/plugins/risk/
src/trading/plugins/brokers/
src/trading/backtest/
src/trading/optimizer/
src/trading/cli/
tests/core/
tests/plugins/data/
tests/plugins/strategies/
tests/plugins/risk/
tests/plugins/brokers/
```

**Step 3: Initialize uv and install dependencies**

Run: `uv sync --all-extras`
Expected: Dependencies install successfully, `.venv` created.

**Step 4: Verify pytest runs**

Run: `uv run pytest --co`
Expected: "no tests ran" (collected 0 items) — no errors.

**Step 5: Commit**

```bash
git add pyproject.toml src/ tests/ uv.lock
git commit -m "feat: project scaffolding with uv and directory structure"
```

---

### Task 2: Core Data Models

**Files:**
- Create: `src/trading/core/models.py`
- Create: `tests/core/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_models.py
from datetime import date, datetime
from decimal import Decimal

import pytest

from trading.core.models import (
    AssetClass,
    Bar,
    Direction,
    Instrument,
    Order,
    OrderType,
    Position,
    Signal,
    TaxLot,
    Trade,
)


class TestInstrument:
    def test_create_equity(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, exchange="NASDAQ")
        assert inst.symbol == "AAPL"
        assert inst.asset_class == AssetClass.EQUITY
        assert inst.exchange == "NASDAQ"

    def test_create_crypto(self):
        inst = Instrument(symbol="BTC-USD", asset_class=AssetClass.CRYPTO)
        assert inst.symbol == "BTC-USD"
        assert inst.exchange is None

    def test_instrument_equality(self):
        a = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        b = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        assert a == b

    def test_instrument_hash(self):
        a = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        b = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


class TestBar:
    def test_create_bar(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        bar = Bar(
            instrument=inst,
            timestamp=datetime(2026, 2, 28, 16, 0),
            open=185.0,
            high=187.5,
            low=184.0,
            close=186.0,
            volume=50_000_000,
        )
        assert bar.close == 186.0
        assert bar.volume == 50_000_000


class TestSignal:
    def test_create_buy_signal(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        signal = Signal(
            instrument=inst,
            direction=Direction.LONG,
            conviction=0.78,
            rationale="Price crossed above 50-day SMA with strong volume",
            strategy_name="momentum",
            timestamp=datetime(2026, 2, 28, 18, 0),
        )
        assert signal.direction == Direction.LONG
        assert signal.conviction == 0.78

    def test_conviction_must_be_0_to_1(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        with pytest.raises(ValueError):
            Signal(
                instrument=inst,
                direction=Direction.LONG,
                conviction=1.5,
                rationale="test",
                strategy_name="test",
                timestamp=datetime(2026, 2, 28),
            )

    def test_conviction_zero_is_valid(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        signal = Signal(
            instrument=inst,
            direction=Direction.CLOSE,
            conviction=0.0,
            rationale="No signal",
            strategy_name="test",
            timestamp=datetime(2026, 2, 28),
        )
        assert signal.conviction == 0.0


class TestOrder:
    def test_create_limit_order(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        order = Order(
            instrument=inst,
            direction=Direction.LONG,
            quantity=54,
            order_type=OrderType.LIMIT,
            limit_price=185.20,
            rationale="Momentum + value signal, conviction 0.78",
            stop_price=176.00,
        )
        assert order.quantity == 54
        assert order.limit_price == 185.20
        assert order.stop_price == 176.00


class TestTaxLot:
    def test_create_tax_lot(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(
            instrument=inst,
            quantity=54,
            cost_basis=185.20,
            purchase_date=date(2026, 2, 28),
        )
        assert lot.quantity == 54
        assert lot.cost_basis == 185.20

    def test_is_long_term_false_when_recent(self):
        lot = TaxLot(
            instrument=Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY),
            quantity=54,
            cost_basis=185.20,
            purchase_date=date(2026, 2, 28),
        )
        assert lot.is_long_term(as_of=date(2026, 8, 1)) is False

    def test_is_long_term_true_after_one_year(self):
        lot = TaxLot(
            instrument=Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY),
            quantity=54,
            cost_basis=185.20,
            purchase_date=date(2025, 1, 1),
        )
        assert lot.is_long_term(as_of=date(2026, 2, 28)) is True

    def test_days_to_long_term(self):
        lot = TaxLot(
            instrument=Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY),
            quantity=54,
            cost_basis=185.20,
            purchase_date=date(2026, 1, 1),
        )
        # 365 days from Jan 1 = Jan 1 next year. As of Feb 28 that's 306 days away.
        days = lot.days_to_long_term(as_of=date(2026, 2, 28))
        assert days == 307  # Jan 1 2026 + 365 = Jan 1 2027. Jan 1 2027 - Feb 28 2026 = 307

    def test_days_to_long_term_already_qualified(self):
        lot = TaxLot(
            instrument=Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY),
            quantity=54,
            cost_basis=185.20,
            purchase_date=date(2024, 1, 1),
        )
        assert lot.days_to_long_term(as_of=date(2026, 2, 28)) == 0


class TestPosition:
    def test_create_position(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=54, cost_basis=185.20, purchase_date=date(2026, 2, 28))
        pos = Position(instrument=inst, tax_lots=[lot])
        assert pos.total_quantity == 54
        assert pos.average_cost == pytest.approx(185.20)

    def test_position_multiple_lots(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot1 = TaxLot(instrument=inst, quantity=50, cost_basis=180.00, purchase_date=date(2025, 6, 1))
        lot2 = TaxLot(instrument=inst, quantity=30, cost_basis=190.00, purchase_date=date(2026, 1, 15))
        pos = Position(instrument=inst, tax_lots=[lot1, lot2])
        assert pos.total_quantity == 80
        expected_avg = (50 * 180.00 + 30 * 190.00) / 80
        assert pos.average_cost == pytest.approx(expected_avg)

    def test_unrealized_pnl(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.00, purchase_date=date(2026, 1, 1))
        pos = Position(instrument=inst, tax_lots=[lot])
        pnl = pos.unrealized_pnl(current_price=190.00)
        assert pnl == pytest.approx(500.00)  # 50 * (190 - 180)


class TestTrade:
    def test_create_completed_trade(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        trade = Trade(
            instrument=inst,
            direction=Direction.LONG,
            quantity=54,
            entry_price=185.20,
            entry_date=date(2026, 2, 1),
            exit_price=196.00,
            exit_date=date(2026, 2, 28),
        )
        assert trade.realized_pnl == pytest.approx(54 * (196.00 - 185.20))
        assert trade.holding_days == 27
        assert trade.is_long_term is False
        assert trade.return_pct == pytest.approx((196.00 - 185.20) / 185.20 * 100, rel=1e-2)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_models.py -v`
Expected: FAIL with ImportError (modules don't exist yet)

**Step 3: Write minimal implementation**

```python
# src/trading/core/models.py
"""Core data models for the trading system."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class AssetClass(str, Enum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    OPTIONS = "options"
    FUTURES = "futures"
    FOREX = "forex"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class Instrument(BaseModel, frozen=True):
    """A tradeable instrument (stock, crypto, option, etc.)."""

    symbol: str
    asset_class: AssetClass
    exchange: str | None = None

    def __hash__(self) -> int:
        return hash((self.symbol, self.asset_class))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instrument):
            return NotImplemented
        return self.symbol == other.symbol and self.asset_class == other.asset_class


class Bar(BaseModel):
    """OHLCV price bar for a single time period."""

    instrument: Instrument
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class Signal(BaseModel):
    """A trading signal emitted by a strategy."""

    instrument: Instrument
    direction: Direction
    conviction: float = Field(ge=0.0, le=1.0)
    rationale: str
    strategy_name: str
    timestamp: datetime

    @model_validator(mode="after")
    def validate_conviction_range(self) -> Self:
        if not 0.0 <= self.conviction <= 1.0:
            raise ValueError(f"Conviction must be between 0 and 1, got {self.conviction}")
        return self


class Order(BaseModel):
    """A sized order ready for execution."""

    instrument: Instrument
    direction: Direction
    quantity: int
    order_type: OrderType
    limit_price: float | None = None
    stop_price: float | None = None
    rationale: str


class TaxLot(BaseModel):
    """A single purchase lot for tax tracking."""

    instrument: Instrument
    quantity: int
    cost_basis: float
    purchase_date: date

    def is_long_term(self, as_of: date) -> bool:
        """Check if this lot qualifies for long-term capital gains treatment."""
        days_held = (as_of - self.purchase_date).days
        return days_held >= 365

    def days_to_long_term(self, as_of: date) -> int:
        """Days remaining until this lot qualifies for long-term treatment."""
        long_term_date = date(
            self.purchase_date.year + 1,
            self.purchase_date.month,
            self.purchase_date.day,
        )
        remaining = (long_term_date - as_of).days
        return max(0, remaining)


class Position(BaseModel):
    """An open position with one or more tax lots."""

    instrument: Instrument
    tax_lots: list[TaxLot]

    @property
    def total_quantity(self) -> int:
        return sum(lot.quantity for lot in self.tax_lots)

    @property
    def average_cost(self) -> float:
        total_cost = sum(lot.quantity * lot.cost_basis for lot in self.tax_lots)
        return total_cost / self.total_quantity if self.total_quantity > 0 else 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        return self.total_quantity * (current_price - self.average_cost)


class Trade(BaseModel):
    """A completed round-trip trade."""

    instrument: Instrument
    direction: Direction
    quantity: int
    entry_price: float
    entry_date: date
    exit_price: float
    exit_date: date

    @property
    def realized_pnl(self) -> float:
        if self.direction == Direction.LONG:
            return self.quantity * (self.exit_price - self.entry_price)
        else:
            return self.quantity * (self.entry_price - self.exit_price)

    @property
    def holding_days(self) -> int:
        return (self.exit_date - self.entry_date).days

    @property
    def is_long_term(self) -> bool:
        return self.holding_days >= 365

    @property
    def return_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price * 100
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_models.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/core/models.py tests/core/test_models.py
git commit -m "feat: core data models (Instrument, Bar, Signal, Order, Position, TaxLot, Trade)"
```

---

### Task 3: Event Bus

**Files:**
- Create: `src/trading/core/bus.py`
- Create: `tests/core/test_bus.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_bus.py
from trading.core.bus import EventBus


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("signal", lambda event: received.append(event))
        bus.publish("signal", {"ticker": "AAPL"})
        assert received == [{"ticker": "AAPL"}]

    def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []
        bus.subscribe("signal", lambda e: received_a.append(e))
        bus.subscribe("signal", lambda e: received_b.append(e))
        bus.publish("signal", "test")
        assert received_a == ["test"]
        assert received_b == ["test"]

    def test_different_topics(self):
        bus = EventBus()
        signals = []
        orders = []
        bus.subscribe("signal", lambda e: signals.append(e))
        bus.subscribe("order", lambda e: orders.append(e))
        bus.publish("signal", "sig1")
        bus.publish("order", "ord1")
        assert signals == ["sig1"]
        assert orders == ["ord1"]

    def test_no_subscribers(self):
        bus = EventBus()
        # Should not raise
        bus.publish("signal", "test")

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("signal", handler)
        bus.publish("signal", "first")
        bus.unsubscribe("signal", handler)
        bus.publish("signal", "second")
        assert received == ["first"]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_bus.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/core/bus.py
"""In-process event bus for connecting pipeline stages."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Simple pub/sub event bus. Handlers are called synchronously."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._handlers[topic].remove(handler)

    def publish(self, topic: str, event: Any) -> None:
        for handler in self._handlers[topic]:
            handler(event)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_bus.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/core/bus.py tests/core/test_bus.py
git commit -m "feat: in-process event bus for pipeline communication"
```

---

### Task 4: Plugin Protocols (Data Provider, Strategy, Risk Manager, Broker)

**Files:**
- Create: `src/trading/plugins/data/base.py`
- Create: `src/trading/plugins/strategies/base.py`
- Create: `src/trading/plugins/risk/base.py`
- Create: `src/trading/plugins/brokers/base.py`
- Create: `tests/plugins/test_protocols.py`

**Step 1: Write the failing tests**

These tests verify that the protocols exist and that concrete implementations can satisfy them.

```python
# tests/plugins/test_protocols.py
from datetime import date, datetime
from typing import runtime_checkable

import pandas as pd

from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    Order,
    OrderType,
    Signal,
)
from trading.plugins.brokers.base import Broker
from trading.plugins.data.base import DataProvider
from trading.plugins.risk.base import RiskManager
from trading.plugins.strategies.base import Strategy


class TestDataProviderProtocol:
    def test_protocol_exists(self):
        assert hasattr(DataProvider, "fetch_bars")
        assert hasattr(DataProvider, "name")

    def test_concrete_implementation_satisfies_protocol(self):
        class FakeProvider:
            @property
            def name(self) -> str:
                return "fake"

            def fetch_bars(
                self,
                instrument: Instrument,
                start: date,
                end: date,
            ) -> pd.DataFrame:
                return pd.DataFrame()

        provider = FakeProvider()
        assert isinstance(provider, DataProvider)


class TestStrategyProtocol:
    def test_protocol_exists(self):
        assert hasattr(Strategy, "generate_signals")
        assert hasattr(Strategy, "name")

    def test_concrete_implementation_satisfies_protocol(self):
        class FakeStrategy:
            @property
            def name(self) -> str:
                return "fake"

            def generate_signals(
                self, instrument: Instrument, bars: pd.DataFrame
            ) -> list[Signal]:
                return []

        strategy = FakeStrategy()
        assert isinstance(strategy, Strategy)


class TestRiskManagerProtocol:
    def test_protocol_exists(self):
        assert hasattr(RiskManager, "evaluate")
        assert hasattr(RiskManager, "name")


class TestBrokerProtocol:
    def test_protocol_exists(self):
        assert hasattr(Broker, "present_order")
        assert hasattr(Broker, "name")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/plugins/test_protocols.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementations**

```python
# src/trading/plugins/data/base.py
"""DataProvider protocol — all data source plugins implement this."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument


@runtime_checkable
class DataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_bars(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars. Returns DataFrame with columns: open, high, low, close, volume.
        Index is datetime."""
        ...
```

```python
# src/trading/plugins/strategies/base.py
"""Strategy protocol — all strategy plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument, Signal


@runtime_checkable
class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        """Analyze price bars and emit trading signals."""
        ...
```

```python
# src/trading/plugins/risk/base.py
"""RiskManager protocol — all risk management plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trading.core.models import Order, Position, Signal


@runtime_checkable
class RiskManager(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(
        self,
        signal: Signal,
        current_price: float,
        positions: list[Position],
        cash: float,
    ) -> Order | None:
        """Evaluate a signal and return a sized Order, or None to reject."""
        ...
```

```python
# src/trading/plugins/brokers/base.py
"""Broker protocol — all broker plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trading.core.models import Order


@runtime_checkable
class Broker(Protocol):
    @property
    def name(self) -> str: ...

    def present_order(self, order: Order, current_price: float) -> str:
        """Present the order to the user. Returns a formatted playbook string."""
        ...
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/plugins/test_protocols.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/plugins/data/base.py src/trading/plugins/strategies/base.py \
    src/trading/plugins/risk/base.py src/trading/plugins/brokers/base.py \
    tests/plugins/test_protocols.py
git commit -m "feat: plugin protocols for data, strategy, risk, and broker"
```

---

### Task 5: Yahoo Finance Data Provider

**Files:**
- Create: `src/trading/plugins/data/yahoo.py`
- Create: `tests/plugins/data/test_yahoo.py`

**Step 1: Write the failing tests**

```python
# tests/plugins/data/test_yahoo.py
"""Tests for Yahoo Finance data provider.

Uses real yfinance calls for integration tests (marked slow).
Unit tests use mocked data.
"""
from datetime import date, datetime

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument
from trading.plugins.data.base import DataProvider
from trading.plugins.data.yahoo import YahooFinanceProvider


@pytest.fixture
def provider():
    return YahooFinanceProvider()


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, exchange="NASDAQ")


class TestYahooFinanceProvider:
    def test_satisfies_protocol(self, provider):
        assert isinstance(provider, DataProvider)

    def test_name(self, provider):
        assert provider.name == "yahoo"

    @pytest.mark.slow
    def test_fetch_bars_real(self, provider, aapl):
        """Integration test — hits real Yahoo Finance API."""
        bars = provider.fetch_bars(aapl, start=date(2025, 1, 2), end=date(2025, 1, 10))
        assert isinstance(bars, pd.DataFrame)
        assert len(bars) > 0
        assert "open" in bars.columns
        assert "high" in bars.columns
        assert "low" in bars.columns
        assert "close" in bars.columns
        assert "volume" in bars.columns

    def test_fetch_bars_returns_correct_columns(self, provider, aapl, monkeypatch):
        """Unit test with mocked data."""
        mock_data = pd.DataFrame(
            {
                "Open": [185.0],
                "High": [187.0],
                "Low": [184.0],
                "Close": [186.0],
                "Volume": [50000000],
            },
            index=pd.DatetimeIndex([datetime(2026, 2, 28)]),
        )

        def mock_download(*args, **kwargs):
            return mock_data

        monkeypatch.setattr("trading.plugins.data.yahoo.yf.download", mock_download)
        bars = provider.fetch_bars(aapl, start=date(2026, 2, 1), end=date(2026, 2, 28))
        assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
        assert bars.iloc[0]["close"] == 186.0
```

Note: Add `markers` to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "slow: marks tests that hit external APIs (deselect with '-m \"not slow\"')",
]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/plugins/data/test_yahoo.py -v -m "not slow"`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/plugins/data/yahoo.py
"""Yahoo Finance data provider plugin."""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from trading.core.models import Instrument


class YahooFinanceProvider:
    """Fetches OHLCV data from Yahoo Finance (free, daily resolution)."""

    @property
    def name(self) -> str:
        return "yahoo"

    def fetch_bars(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        df = yf.download(
            instrument.symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        # Normalize column names to lowercase
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        # Keep only OHLCV columns
        df = df[["open", "high", "low", "close", "volume"]]
        return df
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/plugins/data/test_yahoo.py -v -m "not slow"`
Expected: All non-slow tests PASS

**Step 5: Commit**

```bash
git add src/trading/plugins/data/yahoo.py tests/plugins/data/test_yahoo.py pyproject.toml
git commit -m "feat: Yahoo Finance data provider plugin"
```

---

### Task 6: Momentum Strategy

**Files:**
- Create: `src/trading/plugins/strategies/momentum.py`
- Create: `tests/plugins/strategies/test_momentum.py`

**Step 1: Write the failing tests**

```python
# tests/plugins/strategies/test_momentum.py
"""Tests for the momentum / trend-following strategy."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from trading.core.models import AssetClass, Direction, Instrument
from trading.plugins.strategies.base import Strategy
from trading.plugins.strategies.momentum import MomentumStrategy


@pytest.fixture
def strategy():
    return MomentumStrategy(short_window=10, long_window=50)


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def make_trending_up_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with a clear uptrend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    # Steady uptrend: 180 → 210 over 80 days
    close = np.linspace(180, 210, n_days) + np.random.default_rng(42).normal(0, 0.5, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


def make_trending_down_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with a clear downtrend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    close = np.linspace(210, 170, n_days) + np.random.default_rng(42).normal(0, 0.5, n_days)
    return pd.DataFrame(
        {
            "open": close + 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


def make_flat_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with no clear trend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    close = 190 + np.random.default_rng(42).normal(0, 1.0, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.3,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


class TestMomentumStrategy:
    def test_satisfies_protocol(self, strategy):
        assert isinstance(strategy, Strategy)

    def test_name(self, strategy):
        assert strategy.name == "momentum"

    def test_uptrend_generates_long_signal(self, strategy, aapl):
        bars = make_trending_up_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.LONG
        assert signals[0].conviction > 0.5
        assert signals[0].strategy_name == "momentum"
        assert "AAPL" in signals[0].rationale

    def test_downtrend_generates_short_or_close_signal(self, strategy, aapl):
        bars = make_trending_down_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction in (Direction.SHORT, Direction.CLOSE)
        assert signals[0].conviction > 0.3

    def test_flat_market_low_conviction(self, strategy, aapl):
        bars = make_flat_bars()
        signals = strategy.generate_signals(aapl, bars)
        # Flat market should produce either no signal or a low-conviction one
        if len(signals) > 0:
            assert signals[0].conviction < 0.5

    def test_insufficient_data_returns_empty(self, strategy, aapl):
        bars = make_trending_up_bars(n_days=5)  # Less than long_window
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_rationale_is_plain_english(self, strategy, aapl):
        bars = make_trending_up_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        rationale = signals[0].rationale
        # Should contain plain-English explanation, not just numbers
        assert len(rationale) > 20
        assert any(word in rationale.lower() for word in ["price", "trend", "above", "average", "moving"])
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/plugins/strategies/test_momentum.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/plugins/strategies/momentum.py
"""Momentum / trend-following strategy plugin.

Generates signals based on moving average crossovers, RSI, and volume confirmation.
Uses plain-English rationale for all signals.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal


class MomentumStrategy:
    """Momentum strategy using SMA crossover with RSI and volume confirmation."""

    def __init__(self, short_window: int = 10, long_window: int = 50) -> None:
        self.short_window = short_window
        self.long_window = long_window

    @property
    def name(self) -> str:
        return "momentum"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        if len(bars) < self.long_window:
            return []

        close = bars["close"]
        volume = bars["volume"]

        # Calculate indicators
        sma_short = close.rolling(window=self.short_window).mean()
        sma_long = close.rolling(window=self.long_window).mean()
        rsi = self._calculate_rsi(close, period=14)
        avg_volume = volume.rolling(window=20).mean()

        latest_close = float(close.iloc[-1])
        latest_sma_short = float(sma_short.iloc[-1])
        latest_sma_long = float(sma_long.iloc[-1])
        latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
        latest_volume = float(volume.iloc[-1])
        latest_avg_volume = float(avg_volume.iloc[-1]) if not np.isnan(avg_volume.iloc[-1]) else latest_volume
        volume_ratio = latest_volume / latest_avg_volume if latest_avg_volume > 0 else 1.0

        # Determine trend direction
        sma_cross_up = latest_sma_short > latest_sma_long
        price_above_long = latest_close > latest_sma_long
        pct_above_long = (latest_close - latest_sma_long) / latest_sma_long * 100

        # Calculate conviction (0-1) based on multiple factors
        conviction = 0.0
        rationale_parts = []

        if sma_cross_up and price_above_long:
            # Bullish
            direction = Direction.LONG

            # SMA crossover strength
            cross_strength = min(abs(pct_above_long) / 5.0, 0.4)
            conviction += cross_strength
            rationale_parts.append(
                f"{instrument.symbol}'s price (${latest_close:.2f}) is trading "
                f"{abs(pct_above_long):.1f}% above its {self.long_window}-day moving average, "
                f"indicating an upward trend"
            )

            # RSI confirmation (30-70 is neutral, we want bullish but not overbought)
            if 50 < latest_rsi < 70:
                rsi_boost = 0.2
                conviction += rsi_boost
                rationale_parts.append(
                    f"Buying momentum is healthy (RSI at {latest_rsi:.0f} — "
                    f"strong but not overbought)"
                )
            elif latest_rsi >= 70:
                conviction += 0.05
                rationale_parts.append(
                    f"Caution: buying momentum is very high (RSI at {latest_rsi:.0f} — "
                    f"approaching overbought territory)"
                )
            else:
                conviction += 0.1
                rationale_parts.append(
                    f"Buying momentum is moderate (RSI at {latest_rsi:.0f})"
                )

            # Volume confirmation
            if volume_ratio > 1.2:
                conviction += 0.2
                rationale_parts.append(
                    f"Trading volume is {volume_ratio:.1f}x higher than average, "
                    f"confirming buyer interest"
                )
            elif volume_ratio > 0.8:
                conviction += 0.1
                rationale_parts.append("Trading volume is near average")
            else:
                rationale_parts.append(
                    f"Trading volume is below average ({volume_ratio:.1f}x), "
                    f"suggesting weak conviction in the move"
                )

        elif not sma_cross_up or not price_above_long:
            # Bearish
            direction = Direction.CLOSE

            cross_strength = min(abs(pct_above_long) / 5.0, 0.4)
            conviction += cross_strength
            rationale_parts.append(
                f"{instrument.symbol}'s price (${latest_close:.2f}) is trading "
                f"{abs(pct_above_long):.1f}% below its {self.long_window}-day moving average, "
                f"indicating a downward trend"
            )

            if latest_rsi < 30:
                conviction += 0.15
                rationale_parts.append(
                    f"Selling pressure is extreme (RSI at {latest_rsi:.0f} — oversold)"
                )
            elif latest_rsi < 50:
                conviction += 0.2
                rationale_parts.append(
                    f"Selling pressure is present (RSI at {latest_rsi:.0f})"
                )
            else:
                conviction += 0.05
                rationale_parts.append(
                    f"Selling pressure is light (RSI at {latest_rsi:.0f})"
                )

            if volume_ratio > 1.2:
                conviction += 0.2
                rationale_parts.append(
                    f"Heavy volume ({volume_ratio:.1f}x average) confirms selling pressure"
                )
            else:
                conviction += 0.05

        conviction = min(conviction, 1.0)

        # Build plain-English rationale
        rationale = ". ".join(rationale_parts) + "."

        timestamp = bars.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        return [
            Signal(
                instrument=instrument,
                direction=direction,
                conviction=round(conviction, 2),
                rationale=rationale,
                strategy_name=self.name,
                timestamp=timestamp,
            )
        ]

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/plugins/strategies/test_momentum.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/plugins/strategies/momentum.py tests/plugins/strategies/test_momentum.py
git commit -m "feat: momentum strategy plugin with plain-English rationale"
```

---

### Task 7: Fixed Stake Risk Manager

**Files:**
- Create: `src/trading/plugins/risk/fixed_stake.py`
- Create: `tests/plugins/risk/test_fixed_stake.py`

**Step 1: Write the failing tests**

```python
# tests/plugins/risk/test_fixed_stake.py
from datetime import date, datetime

import pytest

from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    Order,
    OrderType,
    Position,
    Signal,
    TaxLot,
)
from trading.plugins.risk.base import RiskManager
from trading.plugins.risk.fixed_stake import FixedStakeRiskManager


@pytest.fixture
def risk_mgr():
    return FixedStakeRiskManager(stake=10_000, max_position_pct=0.40)


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


@pytest.fixture
def buy_signal(aapl):
    return Signal(
        instrument=aapl,
        direction=Direction.LONG,
        conviction=0.78,
        rationale="Test signal",
        strategy_name="momentum",
        timestamp=datetime(2026, 2, 28),
    )


class TestFixedStakeRiskManager:
    def test_satisfies_protocol(self, risk_mgr):
        assert isinstance(risk_mgr, RiskManager)

    def test_name(self, risk_mgr):
        assert risk_mgr.name == "fixed_stake"

    def test_sizes_order_correctly(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=10_000,
        )
        assert order is not None
        assert order.instrument.symbol == "AAPL"
        assert order.direction == Direction.LONG
        assert order.order_type == OrderType.LIMIT
        # Max position = 40% of $10k = $4000. At $185.20 that's 21 shares
        assert order.quantity == 21
        assert order.limit_price == pytest.approx(185.20)

    def test_rejects_when_no_cash(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=0,
        )
        assert order is None

    def test_reduces_size_when_limited_cash(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=1000,  # Only $1000 available
        )
        assert order is not None
        assert order.quantity == 5  # $1000 / $185.20 = 5 shares

    def test_includes_stop_price(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=10_000,
        )
        assert order is not None
        assert order.stop_price is not None
        # Default stop at 5% below entry
        assert order.stop_price == pytest.approx(185.20 * 0.95, rel=0.01)

    def test_rationale_includes_sizing_info(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=10_000,
        )
        assert order is not None
        assert "21 shares" in order.rationale or "21" in order.rationale
        assert "$" in order.rationale

    def test_close_signal_for_existing_position(self, risk_mgr, aapl):
        signal = Signal(
            instrument=aapl,
            direction=Direction.CLOSE,
            conviction=0.65,
            rationale="Downtrend detected",
            strategy_name="momentum",
            timestamp=datetime(2026, 2, 28),
        )
        lot = TaxLot(instrument=aapl, quantity=50, cost_basis=180.0, purchase_date=date(2026, 1, 1))
        position = Position(instrument=aapl, tax_lots=[lot])
        order = risk_mgr.evaluate(
            signal=signal,
            current_price=190.0,
            positions=[position],
            cash=5000,
        )
        assert order is not None
        assert order.direction == Direction.CLOSE
        assert order.quantity == 50  # Close the full position
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/plugins/risk/test_fixed_stake.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/plugins/risk/fixed_stake.py
"""Fixed stake risk manager — sizes positions based on a fixed dollar stake."""

from __future__ import annotations

import math

from trading.core.models import Direction, Order, OrderType, Position, Signal


class FixedStakeRiskManager:
    """Sizes positions as a percentage of a fixed stake amount.

    Args:
        stake: Total capital allocated to trading (e.g., $10,000)
        max_position_pct: Maximum percentage of stake for a single position (default 40%)
        stop_loss_pct: Default stop-loss percentage below entry (default 5%)
    """

    def __init__(
        self,
        stake: float = 10_000,
        max_position_pct: float = 0.40,
        stop_loss_pct: float = 0.05,
    ) -> None:
        self.stake = stake
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct

    @property
    def name(self) -> str:
        return "fixed_stake"

    def evaluate(
        self,
        signal: Signal,
        current_price: float,
        positions: list[Position],
        cash: float,
    ) -> Order | None:
        if signal.direction == Direction.CLOSE:
            return self._handle_close(signal, current_price, positions)

        return self._handle_entry(signal, current_price, cash)

    def _handle_entry(
        self, signal: Signal, current_price: float, cash: float
    ) -> Order | None:
        if cash <= 0 or current_price <= 0:
            return None

        max_dollars = self.stake * self.max_position_pct
        available = min(max_dollars, cash)
        quantity = math.floor(available / current_price)

        if quantity <= 0:
            return None

        position_value = quantity * current_price
        stop_price = round(current_price * (1 - self.stop_loss_pct), 2)
        max_loss = quantity * current_price * self.stop_loss_pct

        rationale = (
            f"Position size: {quantity} shares at ${current_price:.2f} "
            f"= ${position_value:,.0f} "
            f"({position_value / self.stake * 100:.0f}% of ${self.stake:,.0f} stake). "
            f"Stop-loss at ${stop_price:.2f} limits downside to ${max_loss:,.0f}."
        )

        return Order(
            instrument=signal.instrument,
            direction=signal.direction,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=current_price,
            stop_price=stop_price,
            rationale=rationale,
        )

    def _handle_close(
        self, signal: Signal, current_price: float, positions: list[Position]
    ) -> Order | None:
        matching = [p for p in positions if p.instrument == signal.instrument]
        if not matching:
            return None

        position = matching[0]
        quantity = position.total_quantity
        position_value = quantity * current_price
        pnl = position.unrealized_pnl(current_price)

        rationale = (
            f"Close {quantity} shares of {signal.instrument.symbol} at ${current_price:.2f} "
            f"= ${position_value:,.0f}. "
            f"Unrealized P&L: ${pnl:+,.0f}."
        )

        return Order(
            instrument=signal.instrument,
            direction=Direction.CLOSE,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=current_price,
            rationale=rationale,
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/plugins/risk/test_fixed_stake.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/plugins/risk/fixed_stake.py tests/plugins/risk/test_fixed_stake.py
git commit -m "feat: fixed stake risk manager with position sizing and stop-loss"
```

---

### Task 8: Manual Broker (Action Playbook Generator)

**Files:**
- Create: `src/trading/plugins/brokers/manual.py`
- Create: `tests/plugins/brokers/test_manual.py`

**Step 1: Write the failing tests**

```python
# tests/plugins/brokers/test_manual.py
from datetime import datetime

from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    Order,
    OrderType,
)
from trading.plugins.brokers.base import Broker
from trading.plugins.brokers.manual import ManualBroker


def make_buy_order() -> Order:
    inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, exchange="NASDAQ")
    return Order(
        instrument=inst,
        direction=Direction.LONG,
        quantity=54,
        order_type=OrderType.LIMIT,
        limit_price=185.20,
        stop_price=176.00,
        rationale="Position size: 54 shares at $185.20 = $10,001. Stop at $176.00.",
    )


def make_sell_order() -> Order:
    inst = Instrument(symbol="MSFT", asset_class=AssetClass.EQUITY, exchange="NASDAQ")
    return Order(
        instrument=inst,
        direction=Direction.CLOSE,
        quantity=30,
        order_type=OrderType.LIMIT,
        limit_price=418.50,
        rationale="Close 30 shares of MSFT. Unrealized P&L: +$1,200.",
    )


class TestManualBroker:
    def test_satisfies_protocol(self):
        broker = ManualBroker()
        assert isinstance(broker, Broker)

    def test_name(self):
        assert ManualBroker().name == "manual"

    def test_buy_playbook_contains_action(self):
        broker = ManualBroker()
        playbook = broker.present_order(make_buy_order(), current_price=186.05)
        assert "BUY" in playbook.upper() or "Buy" in playbook
        assert "AAPL" in playbook
        assert "54" in playbook

    def test_buy_playbook_contains_step_by_step(self):
        broker = ManualBroker()
        playbook = broker.present_order(make_buy_order(), current_price=186.05)
        # Should have numbered steps
        assert "1." in playbook or "Step 1" in playbook

    def test_buy_playbook_contains_risk_framing(self):
        broker = ManualBroker()
        playbook = broker.present_order(make_buy_order(), current_price=186.05)
        lower = playbook.lower()
        assert "risk" in lower or "stop" in lower or "loss" in lower or "wrong" in lower

    def test_sell_playbook_contains_action(self):
        broker = ManualBroker()
        playbook = broker.present_order(make_sell_order(), current_price=420.00)
        assert "MSFT" in playbook
        assert "30" in playbook
        assert "SELL" in playbook.upper() or "Sell" in playbook or "Close" in playbook

    def test_playbook_is_plain_english(self):
        broker = ManualBroker()
        playbook = broker.present_order(make_buy_order(), current_price=186.05)
        # Should be readable text, not a data dump
        assert len(playbook) > 100
        # Should contain human-readable words
        assert any(word in playbook.lower() for word in ["shares", "order", "price", "limit"])
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/plugins/brokers/test_manual.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/plugins/brokers/manual.py
"""Manual broker plugin — generates Action Playbooks for the user to execute."""

from __future__ import annotations

from trading.core.models import Direction, Order


class ManualBroker:
    """Generates step-by-step Action Playbooks instead of executing trades.

    The user reads the playbook and places the order manually at their broker.
    """

    @property
    def name(self) -> str:
        return "manual"

    def present_order(self, order: Order, current_price: float) -> str:
        if order.direction in (Direction.LONG, Direction.SHORT):
            return self._buy_playbook(order, current_price)
        else:
            return self._sell_playbook(order, current_price)

    def _buy_playbook(self, order: Order, current_price: float) -> str:
        action = "Buy" if order.direction == Direction.LONG else "Short sell"
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price
        position_value = qty * limit
        stop = order.stop_price

        lines = [
            f"{'=' * 55}",
            f"  ACTION PLAYBOOK: {action} {symbol}",
            f"{'=' * 55}",
            "",
            "WHAT TO DO:",
            f"  1. Open your broker → Trade → Stocks",
            f"  2. Enter: {action} {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f} (current price is ${current_price:.2f})",
            f"  5. Time in force: Good 'til Canceled (GTC)",
            f"  6. Review and submit",
            "",
            "WHY:",
            f"  {order.rationale}",
            "",
            "WHAT COULD GO WRONG:",
        ]

        # Risk scenarios at 5%, 10%, 25% drops
        for pct, label in [(0.05, "5%"), (0.10, "10%"), (0.25, "25%")]:
            drop_price = limit * (1 - pct)
            loss = qty * limit * pct
            lines.append(
                f"  - If {symbol} drops {label} to ${drop_price:.2f}: "
                f"you lose ~${loss:,.0f}"
            )

        if stop:
            stop_loss = qty * (limit - stop)
            lines.extend([
                "",
                "STOP-LOSS:",
                f"  Set a stop-loss order at ${stop:.2f} to limit your downside "
                f"to ~${stop_loss:,.0f}.",
                f"  In your broker: Trade → {symbol} → Sell → Stop order at ${stop:.2f}",
            ])

        return "\n".join(lines)

    def _sell_playbook(self, order: Order, current_price: float) -> str:
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price
        position_value = qty * limit

        lines = [
            f"{'=' * 55}",
            f"  ACTION PLAYBOOK: Sell {symbol}",
            f"{'=' * 55}",
            "",
            "WHAT TO DO:",
            f"  1. Open your broker → Trade → Stocks",
            f"  2. Enter: Sell {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f} (current price is ${current_price:.2f})",
            f"  5. Time in force: Day",
            f"  6. Review and submit",
            "",
            "WHY:",
            f"  {order.rationale}",
        ]

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/plugins/brokers/test_manual.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/plugins/brokers/manual.py tests/plugins/brokers/test_manual.py
git commit -m "feat: manual broker plugin with Action Playbook generation"
```

---

### Task 9: Configuration System

**Files:**
- Create: `src/trading/core/config.py`
- Create: `tests/core/test_config.py`
- Create: `config.example.toml`

**Step 1: Write the failing tests**

```python
# tests/core/test_config.py
import os
from pathlib import Path

import pytest

from trading.core.config import TradingConfig, load_config


class TestTradingConfig:
    def test_default_config(self):
        config = TradingConfig()
        assert config.stake == 10_000
        assert config.data_provider == "yahoo"
        assert config.strategies == ["momentum"]
        assert config.risk_manager == "fixed_stake"
        assert config.broker == "manual"

    def test_custom_config(self):
        config = TradingConfig(
            stake=5_000,
            strategies=["momentum", "mean_reversion"],
            watchlist=["AAPL", "MSFT", "GOOG"],
        )
        assert config.stake == 5_000
        assert len(config.strategies) == 2
        assert config.watchlist == ["AAPL", "MSFT", "GOOG"]


class TestLoadConfig:
    def test_load_from_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[trading]\n'
            'stake = 5000\n'
            'watchlist = ["AAPL", "GOOG"]\n'
            'strategies = ["momentum"]\n'
        )
        config = load_config(config_file)
        assert config.stake == 5_000
        assert config.watchlist == ["AAPL", "GOOG"]

    def test_load_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.stake == 10_000

    def test_watchlist_default_empty(self):
        config = TradingConfig()
        assert config.watchlist == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_config.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add `tomli` to pyproject.toml dependencies (for Python < 3.11 compat, though 3.12 has tomllib):

```python
# src/trading/core/config.py
"""Configuration loading and validation."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TradingConfig(BaseModel):
    """Trading system configuration."""

    stake: float = 10_000
    max_position_pct: float = 0.40
    stop_loss_pct: float = 0.05
    data_provider: str = "yahoo"
    strategies: list[str] = Field(default_factory=lambda: ["momentum"])
    risk_manager: str = "fixed_stake"
    broker: str = "manual"
    watchlist: list[str] = Field(default_factory=list)


def load_config(path: Path) -> TradingConfig:
    """Load config from a TOML file. Returns defaults if file doesn't exist."""
    if not path.exists():
        return TradingConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    trading_data: dict[str, Any] = data.get("trading", {})
    return TradingConfig(**trading_data)
```

Create example config:

```toml
# config.example.toml
# Copy this to config.toml and customize.

[trading]
stake = 10000
max_position_pct = 0.40
stop_loss_pct = 0.05
data_provider = "yahoo"
strategies = ["momentum"]
risk_manager = "fixed_stake"
broker = "manual"
watchlist = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_config.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/core/config.py tests/core/test_config.py config.example.toml
git commit -m "feat: configuration system with TOML loading and defaults"
```

---

### Task 10: Pipeline Engine

**Files:**
- Create: `src/trading/core/engine.py`
- Create: `tests/core/test_engine.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_engine.py
"""Tests for the pipeline engine that wires plugins together."""
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    Order,
    OrderType,
    Signal,
)


class FakeDataProvider:
    @property
    def name(self) -> str:
        return "fake"

    def fetch_bars(self, instrument, start, end) -> pd.DataFrame:
        # Return 80 days of uptrending data
        dates = pd.date_range(start="2026-01-01", periods=80, freq="B")
        close = np.linspace(180, 210, 80)
        return pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [50_000_000] * 80,
            },
            index=dates,
        )


class EmptyDataProvider:
    @property
    def name(self) -> str:
        return "empty"

    def fetch_bars(self, instrument, start, end) -> pd.DataFrame:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


class FakeStrategy:
    @property
    def name(self) -> str:
        return "fake_momentum"

    def generate_signals(self, instrument, bars) -> list[Signal]:
        if len(bars) == 0:
            return []
        return [
            Signal(
                instrument=instrument,
                direction=Direction.LONG,
                conviction=0.78,
                rationale="Test bullish signal",
                strategy_name=self.name,
                timestamp=datetime(2026, 2, 28),
            )
        ]


class FakeRiskManager:
    @property
    def name(self) -> str:
        return "fake_risk"

    def evaluate(self, signal, current_price, positions, cash) -> Order | None:
        return Order(
            instrument=signal.instrument,
            direction=signal.direction,
            quantity=54,
            order_type=OrderType.LIMIT,
            limit_price=current_price,
            stop_price=current_price * 0.95,
            rationale="Test order",
        )


class FakeBroker:
    @property
    def name(self) -> str:
        return "fake_broker"

    def present_order(self, order, current_price) -> str:
        return f"BUY {order.quantity} shares of {order.instrument.symbol}"


@pytest.fixture
def engine():
    return TradingEngine(
        data_provider=FakeDataProvider(),
        strategies=[FakeStrategy()],
        risk_manager=FakeRiskManager(),
        broker=FakeBroker(),
        config=TradingConfig(watchlist=["AAPL", "MSFT"]),
    )


class TestTradingEngine:
    def test_scan_returns_results(self, engine):
        results = engine.scan()
        assert len(results) > 0

    def test_scan_result_has_signal_and_playbook(self, engine):
        results = engine.scan()
        for result in results:
            assert "signal" in result
            assert "playbook" in result
            assert "order" in result
            assert result["signal"].conviction > 0

    def test_scan_covers_all_watchlist(self, engine):
        results = engine.scan()
        symbols = {r["signal"].instrument.symbol for r in results}
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_scan_with_empty_data(self):
        engine = TradingEngine(
            data_provider=EmptyDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(watchlist=["AAPL"]),
        )
        results = engine.scan()
        assert results == []

    def test_scan_explain_single_instrument(self, engine):
        results = engine.scan(symbols=["AAPL"])
        assert len(results) == 1
        assert results[0]["signal"].instrument.symbol == "AAPL"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_engine.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/core/engine.py
"""Pipeline engine — orchestrates data fetch → signal → risk → order presentation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from trading.core.config import TradingConfig
from trading.core.models import AssetClass, Instrument, Position


class TradingEngine:
    """Wires plugins together and runs the trading pipeline."""

    def __init__(
        self,
        data_provider: Any,
        strategies: list[Any],
        risk_manager: Any,
        broker: Any,
        config: TradingConfig,
        positions: list[Position] | None = None,
        cash: float | None = None,
    ) -> None:
        self.data_provider = data_provider
        self.strategies = strategies
        self.risk_manager = risk_manager
        self.broker = broker
        self.config = config
        self.positions = positions or []
        self.cash = cash if cash is not None else config.stake

    def scan(
        self,
        symbols: list[str] | None = None,
        lookback_days: int = 120,
    ) -> list[dict[str, Any]]:
        """Run the full pipeline for the watchlist (or a subset of symbols).

        Returns a list of dicts with keys: signal, order, playbook.
        """
        target_symbols = symbols or self.config.watchlist
        if not target_symbols:
            return []

        end = date.today()
        start = end - timedelta(days=lookback_days)
        results = []

        for symbol in target_symbols:
            instrument = Instrument(symbol=symbol, asset_class=AssetClass.EQUITY)

            # Stage 1: Fetch data
            bars = self.data_provider.fetch_bars(instrument, start, end)
            if bars.empty:
                continue

            # Stage 2: Generate signals from all strategies
            for strategy in self.strategies:
                signals = strategy.generate_signals(instrument, bars)

                for signal in signals:
                    current_price = float(bars["close"].iloc[-1])

                    # Stage 3: Risk filtering and sizing
                    order = self.risk_manager.evaluate(
                        signal=signal,
                        current_price=current_price,
                        positions=self.positions,
                        cash=self.cash,
                    )

                    if order is None:
                        continue

                    # Stage 4: Generate playbook
                    playbook = self.broker.present_order(order, current_price)

                    results.append({
                        "signal": signal,
                        "order": order,
                        "playbook": playbook,
                    })

        return results
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_engine.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trading/core/engine.py tests/core/test_engine.py
git commit -m "feat: pipeline engine orchestrating data → signal → risk → playbook"
```

---

### Task 11: CLI — `trading scan` Command

**Files:**
- Create: `src/trading/cli/main.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_cli.py`

**Step 1: Write the failing tests**

```python
# tests/cli/test_cli.py
from unittest.mock import patch

from typer.testing import CliRunner

from trading.cli.main import app

runner = CliRunner()


class TestCLIScan:
    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower() or "Scan" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_shows_output(self, mock_build):
        """Test that scan produces output when there are signals."""
        from datetime import datetime
        from trading.core.models import (
            AssetClass,
            Direction,
            Instrument,
            Order,
            OrderType,
            Signal,
        )

        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = [
            {
                "signal": Signal(
                    instrument=inst,
                    direction=Direction.LONG,
                    conviction=0.78,
                    rationale="Test rationale",
                    strategy_name="momentum",
                    timestamp=datetime(2026, 2, 28),
                ),
                "order": Order(
                    instrument=inst,
                    direction=Direction.LONG,
                    quantity=54,
                    order_type=OrderType.LIMIT,
                    limit_price=185.20,
                    stop_price=176.00,
                    rationale="54 shares",
                ),
                "playbook": "BUY 54 shares of AAPL at $185.20",
            }
        ]

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "AAPL" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_no_signals(self, mock_build):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = []
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "No" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_with_explain(self, mock_build):
        from datetime import datetime
        from trading.core.models import (
            AssetClass,
            Direction,
            Instrument,
            Order,
            OrderType,
            Signal,
        )

        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = [
            {
                "signal": Signal(
                    instrument=inst,
                    direction=Direction.LONG,
                    conviction=0.78,
                    rationale="Detailed test rationale for AAPL",
                    strategy_name="momentum",
                    timestamp=datetime(2026, 2, 28),
                ),
                "order": Order(
                    instrument=inst,
                    direction=Direction.LONG,
                    quantity=54,
                    order_type=OrderType.LIMIT,
                    limit_price=185.20,
                    rationale="54 shares at $185.20",
                ),
                "playbook": "Full playbook here",
            }
        ]

        result = runner.invoke(app, ["scan", "--explain", "AAPL"])
        assert result.exit_code == 0
        assert "AAPL" in result.output
        # Explain mode should show the full playbook
        assert "playbook" in result.output.lower() or "Full playbook" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_cli.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/trading/cli/main.py
"""CLI entry point for the trading system."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading.core.config import TradingConfig, load_config
from trading.core.engine import TradingEngine
from trading.plugins.brokers.manual import ManualBroker
from trading.plugins.data.yahoo import YahooFinanceProvider
from trading.plugins.risk.fixed_stake import FixedStakeRiskManager
from trading.plugins.strategies.momentum import MomentumStrategy

app = typer.Typer(help="Hybrid trading system — automated signals, manual execution.")
console = Console()


def _build_engine(config_path: Path = Path("config.toml")) -> TradingEngine:
    """Build the trading engine from config, wiring up all plugins."""
    config = load_config(config_path)

    data_provider = YahooFinanceProvider()

    strategy_map = {
        "momentum": MomentumStrategy,
    }
    strategies = [strategy_map[name]() for name in config.strategies if name in strategy_map]

    risk_manager = FixedStakeRiskManager(
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
    )

    broker = ManualBroker()

    return TradingEngine(
        data_provider=data_provider,
        strategies=strategies,
        risk_manager=risk_manager,
        broker=broker,
        config=config,
    )


@app.command()
def scan(
    explain: Optional[str] = typer.Option(
        None, "--explain", help="Show full playbook for a specific symbol"
    ),
    config: Path = typer.Option(
        Path("config.toml"), "--config", "-c", help="Path to config file"
    ),
) -> None:
    """Run the pipeline and show today's signals."""
    engine = _build_engine(config)

    symbols = [explain] if explain else None
    results = engine.scan(symbols=symbols)

    if not results:
        console.print("\n[dim]No actionable signals found today.[/dim]\n")
        return

    if explain:
        # Show full playbook for the explained symbol
        for result in results:
            sig = result["signal"]
            console.print()
            console.print(
                Panel(
                    result["playbook"],
                    title=f"[bold]{sig.direction.value.upper()} {sig.instrument.symbol}[/bold]",
                    subtitle=f"conviction: {sig.conviction:.0%} | strategy: {sig.strategy_name}",
                )
            )
            console.print(f"\n[bold]Rationale:[/bold] {sig.rationale}\n")
        return

    # Summary table
    table = Table(title="Today's Signals")
    table.add_column("Action", style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Conviction")
    table.add_column("Qty")
    table.add_column("Limit Price")
    table.add_column("Strategy")
    table.add_column("Summary")

    for result in results:
        sig = result["signal"]
        order = result["order"]
        direction = sig.direction.value.upper()

        # Color-code direction
        if sig.direction.value == "long":
            style = "green"
        elif sig.direction.value == "close":
            style = "red"
        else:
            style = "yellow"

        # Truncate rationale for table
        summary = sig.rationale[:60] + "..." if len(sig.rationale) > 60 else sig.rationale

        table.add_row(
            f"[{style}]{direction}[/{style}]",
            sig.instrument.symbol,
            f"{sig.conviction:.0%}",
            str(order.quantity),
            f"${order.limit_price:.2f}" if order.limit_price else "—",
            sig.strategy_name,
            summary,
        )

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Use [bold]trading scan --explain SYMBOL[/bold] for full playbook.[/dim]\n"
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_cli.py -v`
Expected: All tests PASS

**Step 5: Verify CLI works end-to-end**

Run: `uv run trading scan --help`
Expected: Help text showing scan command options.

Run: `uv run trading scan --config config.example.toml`
Expected: Either a table of signals or "No actionable signals" (depending on current market conditions). This is a live integration test.

**Step 6: Commit**

```bash
git add src/trading/cli/main.py tests/cli/__init__.py tests/cli/test_cli.py
git commit -m "feat: CLI with 'trading scan' command and rich output"
```

---

### Task 12: Run Full Test Suite and Verify

**Step 1: Run all tests**

Run: `uv run pytest -v --tb=short`
Expected: All tests PASS

**Step 2: Run with coverage**

Run: `uv run pytest --cov=trading --cov-report=term-missing`
Expected: Coverage report showing coverage for all modules.

**Step 3: Final commit if any fixups needed**

If any tests fail or need adjustment, fix and commit:
```bash
git add -A
git commit -m "fix: test suite adjustments for Phase 1"
```

---

## Phase 1 Complete — What You Can Do

After implementing this plan, you have a working system that:

```bash
# See today's signals for your watchlist
trading scan --config config.toml

# Get a full Action Playbook for a specific stock
trading scan --explain AAPL --config config.toml
```

## What Comes Next (Future Plans)

- **Phase 2:** Tax-aware risk manager, composite strategy, mean reversion strategy
- **Phase 3:** Backtesting engine with tax-adjusted metrics
- **Phase 4:** Growth optimizer (Kelly allocation, what-if scenarios)
- **Phase 5:** Portfolio tracking and trade journaling
- **Phase 6:** Web dashboard (FastAPI + React)
- **Phase 7:** Alert system (price watchers, notifications)
- **Phase 8:** Multi-user and deployment
