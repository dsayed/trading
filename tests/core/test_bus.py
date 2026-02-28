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
