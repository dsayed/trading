"""Core data models for the trading system."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


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
        days_held = (as_of - self.purchase_date).days
        return days_held >= 365

    def days_to_long_term(self, as_of: date) -> int:
        from datetime import timedelta

        long_term_date = self.purchase_date + timedelta(days=365)
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
        if self.direction == Direction.LONG:
            return (self.exit_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.exit_price) / self.entry_price * 100
