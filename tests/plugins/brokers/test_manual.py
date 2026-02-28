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
        assert len(playbook) > 100
        assert any(word in playbook.lower() for word in ["shares", "order", "price", "limit"])
