"""Tests for the pipeline engine that wires plugins together."""
from datetime import date, datetime
from typing import Any

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
    Position,
    Signal,
)


class FakeDataProvider:
    @property
    def name(self) -> str:
        return "fake"

    def fetch_bars(self, instrument, start, end) -> pd.DataFrame:
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
