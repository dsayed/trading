"""Tests for the CompositeDataProvider."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument, OptionChain, OptionContract
from trading.plugins.data.base import DataProvider, DiscoveryProvider, OptionsDataProvider
from trading.plugins.data.composite import CompositeDataProvider


# ── Fake sub-providers ─────────────────────────────────────────────


class FakeBarsProvider:
    @property
    def name(self) -> str:
        return "fake_bars"

    def fetch_bars(self, instrument, start, end):
        return pd.DataFrame({
            "open": [100.0], "high": [105.0], "low": [99.0],
            "close": [103.0], "volume": [1000000],
        }, index=pd.to_datetime(["2024-01-01"]))


class FakeOptionsProvider:
    @property
    def name(self) -> str:
        return "fake_options"

    def fetch_option_chain(self, instrument, expiration=None):
        return [
            OptionChain(
                instrument=instrument,
                expiration=date(2024, 1, 19),
                calls=[
                    OptionContract(
                        contract_symbol="AAPL240119C190",
                        strike=190.0,
                        expiration=date(2024, 1, 19),
                        option_type="call",
                        bid=5.0, ask=5.5, last_price=5.25,
                        volume=100, open_interest=1000,
                        implied_volatility=0.25, in_the_money=True,
                    )
                ],
                puts=[],
            )
        ]

    def fetch_current_price(self, instrument):
        return 195.50


class FakeDiscoveryProvider:
    @property
    def name(self) -> str:
        return "fake_discovery"

    def list_universe(self, universe_name):
        return ["AAPL", "MSFT", "GOOG"]

    def get_movers(self, direction="gainers", limit=20):
        return [{"symbol": "AAPL", "change_pct": 5.2, "volume": 123456, "price": 190.50}]


INST = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


# ── Protocol conformance ─────────────────────────────────────────────


class TestProtocolConformance:
    def test_implements_data_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())
        assert isinstance(composite, DataProvider)

    def test_implements_options_data_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider(), FakeOptionsProvider())
        assert isinstance(composite, OptionsDataProvider)

    def test_implements_discovery_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider(), discovery_provider=FakeDiscoveryProvider())
        assert isinstance(composite, DiscoveryProvider)


# ── Routing ──────────────────────────────────────────────────────────


class TestRouting:
    def test_fetch_bars_delegates_to_bars_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())

        df = composite.fetch_bars(INST, date(2024, 1, 1), date(2024, 1, 3))

        assert len(df) == 1
        assert df["close"].iloc[0] == 103.0

    def test_fetch_option_chain_delegates_to_options_provider(self):
        composite = CompositeDataProvider(
            FakeBarsProvider(),
            options_provider=FakeOptionsProvider(),
        )

        chains = composite.fetch_option_chain(INST)

        assert len(chains) == 1
        assert chains[0].calls[0].strike == 190.0

    def test_fetch_current_price_delegates_to_options_provider(self):
        composite = CompositeDataProvider(
            FakeBarsProvider(),
            options_provider=FakeOptionsProvider(),
        )

        price = composite.fetch_current_price(INST)

        assert price == 195.50

    def test_list_universe_delegates_to_discovery_provider(self):
        composite = CompositeDataProvider(
            FakeBarsProvider(),
            discovery_provider=FakeDiscoveryProvider(),
        )

        symbols = composite.list_universe("sp500")

        assert symbols == ["AAPL", "MSFT", "GOOG"]

    def test_get_movers_delegates_to_discovery_provider(self):
        composite = CompositeDataProvider(
            FakeBarsProvider(),
            discovery_provider=FakeDiscoveryProvider(),
        )

        movers = composite.get_movers("gainers")

        assert len(movers) == 1
        assert movers[0]["symbol"] == "AAPL"


# ── Missing provider errors ──────────────────────────────────────────


class TestMissingProviderErrors:
    def test_options_raises_without_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())

        with pytest.raises(NotImplementedError, match="No options provider"):
            composite.fetch_option_chain(INST)

    def test_current_price_raises_without_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())

        with pytest.raises(NotImplementedError, match="No options provider"):
            composite.fetch_current_price(INST)

    def test_list_universe_raises_without_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())

        with pytest.raises(NotImplementedError, match="No discovery provider"):
            composite.list_universe("sp500")

    def test_get_movers_raises_without_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())

        with pytest.raises(NotImplementedError, match="No discovery provider"):
            composite.get_movers("gainers")


# ── Name concatenation ───────────────────────────────────────────────


class TestName:
    def test_single_provider(self):
        composite = CompositeDataProvider(FakeBarsProvider())
        assert composite.name == "fake_bars"

    def test_multiple_providers(self):
        composite = CompositeDataProvider(
            FakeBarsProvider(),
            options_provider=FakeOptionsProvider(),
            discovery_provider=FakeDiscoveryProvider(),
        )
        assert composite.name == "fake_bars+fake_options+fake_discovery"

    def test_deduplicates_same_provider(self):
        bars = FakeBarsProvider()
        composite = CompositeDataProvider(bars, options_provider=bars)
        assert composite.name == "fake_bars"


# ── Support flags ────────────────────────────────────────────────────


class TestSupportFlags:
    def test_supports_options_true_when_set(self):
        composite = CompositeDataProvider(FakeBarsProvider(), FakeOptionsProvider())
        assert composite.supports_options is True

    def test_supports_options_false_when_none(self):
        composite = CompositeDataProvider(FakeBarsProvider())
        assert composite.supports_options is False

    def test_supports_discovery_true_when_set(self):
        composite = CompositeDataProvider(FakeBarsProvider(), discovery_provider=FakeDiscoveryProvider())
        assert composite.supports_discovery is True

    def test_supports_discovery_false_when_none(self):
        composite = CompositeDataProvider(FakeBarsProvider())
        assert composite.supports_discovery is False
