from datetime import date, datetime

import pytest

from trading.core.models import (
    AssetClass,
    Bar,
    Direction,
    Instrument,
    OptionChain,
    OptionContract,
    Order,
    OrderType,
    Play,
    PlayType,
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


class TestOptionContract:
    def test_create_option_contract(self):
        contract = OptionContract(
            contract_symbol="AAPL260320C00200000",
            strike=200.0,
            expiration=date(2026, 3, 20),
            option_type="call",
            bid=5.20,
            ask=5.50,
            last_price=5.35,
            volume=1200,
            open_interest=5000,
            implied_volatility=0.32,
            in_the_money=False,
        )
        assert contract.strike == 200.0
        assert contract.option_type == "call"
        assert contract.in_the_money is False

    def test_mid_price(self):
        contract = OptionContract(
            contract_symbol="AAPL260320C00200000",
            strike=200.0,
            expiration=date(2026, 3, 20),
            option_type="call",
            bid=5.20,
            ask=5.50,
            last_price=5.35,
            volume=1200,
            open_interest=5000,
            implied_volatility=0.32,
            in_the_money=False,
        )
        assert contract.mid_price == pytest.approx(5.35)


class TestOptionChain:
    def test_create_option_chain(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        call = OptionContract(
            contract_symbol="AAPL260320C00200000",
            strike=200.0,
            expiration=date(2026, 3, 20),
            option_type="call",
            bid=5.20,
            ask=5.50,
            last_price=5.35,
            volume=1200,
            open_interest=5000,
            implied_volatility=0.32,
            in_the_money=False,
        )
        put = OptionContract(
            contract_symbol="AAPL260320P00180000",
            strike=180.0,
            expiration=date(2026, 3, 20),
            option_type="put",
            bid=2.10,
            ask=2.40,
            last_price=2.25,
            volume=800,
            open_interest=3000,
            implied_volatility=0.28,
            in_the_money=False,
        )
        chain = OptionChain(
            instrument=inst,
            expiration=date(2026, 3, 20),
            calls=[call],
            puts=[put],
        )
        assert len(chain.calls) == 1
        assert len(chain.puts) == 1
        assert chain.expiration == date(2026, 3, 20)


class TestPlay:
    def test_create_play(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=inst, tax_lots=[lot])
        play = Play(
            position=pos,
            play_type=PlayType.COVERED_CALL,
            title="Sell covered calls on AAPL",
            rationale="Generate income on existing position",
            conviction=0.75,
            contracts=1,
            premium=520.0,
            max_profit=2520.0,
            max_loss=None,
            breakeven=174.80,
            playbook="1. Sell to Open 1 AAPL $200 Call\n2. Expiration: Mar 20",
            advisor_name="covered_call",
        )
        assert play.play_type == PlayType.COVERED_CALL
        assert play.conviction == 0.75
        assert play.contracts == 1

    def test_play_with_tax_note(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2026, 1, 1))
        pos = Position(instrument=inst, tax_lots=[lot])
        play = Play(
            position=pos,
            play_type=PlayType.TRIM,
            title="Trim AAPL position",
            rationale="Position up significantly",
            conviction=0.60,
            tax_note="Short-term gains: held < 1 year. Consider waiting 307 days for long-term treatment.",
            playbook="1. Sell 20 shares at market",
            advisor_name="stock_play",
        )
        assert play.tax_note is not None
        assert "short-term" in play.tax_note.lower()

    def test_play_conviction_validation(self):
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        lot = TaxLot(instrument=inst, quantity=50, cost_basis=180.0, purchase_date=date(2026, 1, 1))
        pos = Position(instrument=inst, tax_lots=[lot])
        with pytest.raises(ValueError):
            Play(
                position=pos,
                play_type=PlayType.HOLD,
                title="Hold",
                rationale="No action",
                conviction=1.5,
                playbook="Hold position",
                advisor_name="stock_play",
            )
