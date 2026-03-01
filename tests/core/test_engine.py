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
    Play,
    PlayType,
    Position,
    Signal,
    TaxLot,
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

    def present_order(self, order, current_price, conviction=0.0, strategy_name="") -> str:
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


class FakeStrategyLowConviction:
    """Returns signals with lower conviction for ranking tests."""

    @property
    def name(self) -> str:
        return "fake_low"

    def generate_signals(self, instrument, bars) -> list[Signal]:
        if len(bars) == 0:
            return []
        return [
            Signal(
                instrument=instrument,
                direction=Direction.LONG,
                conviction=0.30,
                rationale="Low conviction signal",
                strategy_name=self.name,
                timestamp=datetime(2026, 2, 28),
            )
        ]


class TestDiscover:
    def test_discover_returns_ranked_results(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy(), FakeStrategyLowConviction()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(["AAPL", "MSFT"])
        assert len(results) > 0
        # Results should be sorted by conviction descending
        convictions = [r["signal"].conviction for r in results]
        assert convictions == sorted(convictions, reverse=True)

    def test_discover_respects_max_results(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy(), FakeStrategyLowConviction()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(["AAPL", "MSFT", "GOOG"], max_results=2)
        assert len(results) <= 2

    def test_discover_filters_by_strategy_name(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy(), FakeStrategyLowConviction()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(
            ["AAPL"], strategy_names=["fake_momentum"]
        )
        assert all(r["signal"].strategy_name == "fake_momentum" for r in results)

    def test_discover_empty_symbols(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover([])
        assert results == []

    def test_discover_forex_symbol(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(["EUR/USD"])
        assert len(results) > 0
        assert results[0]["signal"].instrument.asset_class == AssetClass.FOREX

    def test_discover_with_empty_data(self):
        engine = TradingEngine(
            data_provider=EmptyDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(["AAPL"])
        assert results == []

    def test_discover_unknown_strategy_name(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.discover(["AAPL"], strategy_names=["nonexistent"])
        assert results == []


class FakeAdvisor:
    @property
    def name(self) -> str:
        return "fake_advisor"

    def advise(self, position, bars, option_chains, current_price) -> list[Play]:
        return [
            Play(
                position=position,
                play_type=PlayType.HOLD,
                title=f"Hold {position.instrument.symbol}",
                rationale="Fake hold recommendation",
                conviction=0.50,
                playbook="1. Hold position",
                advisor_name=self.name,
            )
        ]


class TestAdvise:
    def test_advise_returns_results(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=inst, tax_lots=[lot])

        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(watchlist=["AAPL"]),
        )
        results = engine.advise([pos], [FakeAdvisor()])
        assert len(results) == 1
        assert results[0]["position"] == pos
        assert results[0]["current_price"] > 0
        assert len(results[0]["plays"]) == 1

    def test_advise_computes_unrealized_pnl(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=inst, tax_lots=[lot])

        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.advise([pos], [FakeAdvisor()])
        assert results[0]["unrealized_pnl"] != 0  # price != cost basis

    def test_advise_multiple_positions(self):
        inst_a = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        inst_m = Instrument(symbol="MSFT", asset_class=AssetClass.EQUITY)
        lot_a = TaxLot(instrument=inst_a, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        lot_m = TaxLot(instrument=inst_m, quantity=30, cost_basis=300.0, purchase_date=date(2025, 6, 1))

        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.advise(
            [Position(instrument=inst_a, tax_lots=[lot_a]),
             Position(instrument=inst_m, tax_lots=[lot_m])],
            [FakeAdvisor()],
        )
        assert len(results) == 2

    def test_advise_empty_positions(self):
        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.advise([], [FakeAdvisor()])
        assert results == []

    def test_advise_empty_advisors(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=inst, tax_lots=[lot])

        engine = TradingEngine(
            data_provider=FakeDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.advise([pos], [])
        assert results == []

    def test_advise_with_empty_data(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=inst, tax_lots=[lot])

        engine = TradingEngine(
            data_provider=EmptyDataProvider(),
            strategies=[FakeStrategy()],
            risk_manager=FakeRiskManager(),
            broker=FakeBroker(),
            config=TradingConfig(),
        )
        results = engine.advise([pos], [FakeAdvisor()])
        assert len(results) == 1
        assert results[0]["current_price"] == 0.0
