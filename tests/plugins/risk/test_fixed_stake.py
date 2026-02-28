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
            cash=1000,
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
        assert order.stop_price == pytest.approx(185.20 * 0.95, rel=0.01)

    def test_rationale_includes_sizing_info(self, risk_mgr, buy_signal):
        order = risk_mgr.evaluate(
            signal=buy_signal,
            current_price=185.20,
            positions=[],
            cash=10_000,
        )
        assert order is not None
        assert "21" in order.rationale
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
        assert order.quantity == 50
