"""Tests for the Twelve Data provider plugin."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument
from trading.plugins.data.base import DataProvider, OptionsDataProvider
from trading.plugins.data.twelvedata import TwelveDataProvider


# ── Fake TDClient ──────────────────────────────────────────────────


class FakeTimeSeries:
    def __init__(self, df: pd.DataFrame | None):
        self._df = df

    def as_pandas(self):
        return self._df if self._df is not None else pd.DataFrame()


class FakeOptionsChain:
    def __init__(self, data):
        self._data = data

    def as_json(self):
        return self._data


class FakePrice:
    def __init__(self, data):
        self._data = data

    def as_json(self):
        return self._data


class FakeTDClient:
    """Hand-built fake mimicking the twelvedata.TDClient interface."""

    def __init__(self, apikey: str = "test"):
        self.apikey = apikey
        self._bars_df: pd.DataFrame | None = None
        self._options_data: list | dict | None = None
        self._price_data: dict | None = None

    def time_series(self, **kwargs):
        return FakeTimeSeries(self._bars_df)

    def options_chain(self, **kwargs):
        return FakeOptionsChain(self._options_data or [])

    def price(self, **kwargs):
        return FakePrice(self._price_data or {})


def _make_provider(fake_client: FakeTDClient) -> TwelveDataProvider:
    """Build a TwelveDataProvider with an injected fake client."""
    provider = object.__new__(TwelveDataProvider)
    provider._client = fake_client
    provider._calls_per_minute = 8
    provider._call_times = []
    return provider


# ── Protocol conformance ─────────────────────────────────────────────


class TestProtocolConformance:
    def test_implements_data_provider(self):
        provider = _make_provider(FakeTDClient())
        assert isinstance(provider, DataProvider)

    def test_implements_options_data_provider(self):
        provider = _make_provider(FakeTDClient())
        assert isinstance(provider, OptionsDataProvider)

    def test_name(self):
        provider = _make_provider(FakeTDClient())
        assert provider.name == "twelvedata"


# ── fetch_bars ───────────────────────────────────────────────────────


class TestFetchBars:
    def test_returns_ohlcv_dataframe(self):
        client = FakeTDClient()
        client._bars_df = pd.DataFrame({
            "Open": [100.0, 103.0, 106.0],
            "High": [105.0, 107.0, 108.0],
            "Low": [99.0, 102.0, 104.0],
            "Close": [103.0, 106.0, 107.5],
            "Volume": [1000000, 1200000, 900000],
        }, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert len(df) == 3
        assert "close" in df.columns
        assert df["close"].iloc[-1] == 107.5

    def test_empty_when_no_data(self):
        client = FakeTDClient()
        client._bars_df = pd.DataFrame()
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert df.empty

    def test_handles_none_response(self):
        client = FakeTDClient()
        client._bars_df = None
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert df.empty


# ── fetch_option_chain ───────────────────────────────────────────────


class TestFetchOptionChain:
    def test_returns_grouped_chains(self):
        client = FakeTDClient()
        client._options_data = [
            {
                "contract_name": "AAPL240119C190",
                "strike": 190.0,
                "expiration_date": "2024-01-19",
                "option_type": "call",
                "bid": 5.0,
                "ask": 5.5,
                "last_price": 5.25,
                "volume": 100,
                "open_interest": 1000,
                "implied_volatility": 0.25,
                "in_the_money": True,
            },
            {
                "contract_name": "AAPL240119P190",
                "strike": 190.0,
                "expiration_date": "2024-01-19",
                "option_type": "put",
                "bid": 3.0,
                "ask": 3.5,
                "last_price": 3.25,
                "volume": 50,
                "open_interest": 500,
                "implied_volatility": 0.28,
                "in_the_money": False,
            },
        ]
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert len(chains) == 1
        assert chains[0].expiration == date(2024, 1, 19)
        assert len(chains[0].calls) == 1
        assert len(chains[0].puts) == 1

    def test_empty_on_no_data(self):
        client = FakeTDClient()
        client._options_data = []
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert chains == []


# ── fetch_current_price ──────────────────────────────────────────────


class TestFetchCurrentPrice:
    def test_returns_price(self):
        client = FakeTDClient()
        client._price_data = {"price": "195.50"}
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 195.50

    def test_returns_zero_on_error(self):
        client = FakeTDClient()

        def raise_error(**kwargs):
            raise Exception("API error")

        client.price = raise_error
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 0.0


# ── Constructor ───────────────────────────────────────────────────────


class TestConstructor:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Twelve Data API key required"):
            TwelveDataProvider()
