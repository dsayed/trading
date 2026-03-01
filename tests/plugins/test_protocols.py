from datetime import date, datetime

import pandas as pd

from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    OptionChain,
    Order,
    OrderType,
    Play,
    PlayType,
    Position,
    Signal,
    TaxLot,
)
from trading.plugins.advisors.base import PositionAdvisor
from trading.plugins.brokers.base import Broker
from trading.plugins.data.base import DataProvider, OptionsDataProvider
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

            def fetch_bars(self, instrument, start, end):
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

            def generate_signals(self, instrument, bars):
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


class TestOptionsDataProviderProtocol:
    def test_protocol_exists(self):
        assert hasattr(OptionsDataProvider, "fetch_option_chain")
        assert hasattr(OptionsDataProvider, "fetch_current_price")

    def test_concrete_implementation_satisfies_protocol(self):
        class FakeOptionsProvider:
            def fetch_option_chain(self, instrument, expiration=None):
                return []

            def fetch_current_price(self, instrument):
                return 100.0

        provider = FakeOptionsProvider()
        assert isinstance(provider, OptionsDataProvider)


class TestPositionAdvisorProtocol:
    def test_protocol_exists(self):
        assert hasattr(PositionAdvisor, "advise")
        assert hasattr(PositionAdvisor, "name")

    def test_concrete_implementation_satisfies_protocol(self):
        class FakeAdvisor:
            @property
            def name(self) -> str:
                return "fake"

            def advise(self, position, bars, option_chains, current_price):
                return []

        advisor = FakeAdvisor()
        assert isinstance(advisor, PositionAdvisor)
