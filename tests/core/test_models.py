from datetime import date, datetime

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
        days = lot.days_to_long_term(as_of=date(2026, 2, 28))
        assert days == 307

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
        assert pnl == pytest.approx(500.00)


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
