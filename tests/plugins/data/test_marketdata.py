"""Tests for the MarketData.app data provider plugin."""

from __future__ import annotations

from datetime import date

import pytest

from trading.core.models import AssetClass, Instrument
from trading.plugins.data.base import DataProvider, OptionsDataProvider
from trading.plugins.data.marketdata import MarketDataProvider


# ── Fake HTTP session ──────────────────────────────────────────────


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeSession:
    """Hand-built fake for requests.Session."""

    def __init__(self):
        self.responses: dict[str, FakeResponse] = {}
        self.headers: dict[str, str] = {}

    def get(self, url: str, params=None, timeout=None):
        for key, resp in self.responses.items():
            if key in url:
                return resp
        return FakeResponse({"s": "no_data"})


def _make_provider(fake_session: FakeSession) -> MarketDataProvider:
    """Build a MarketDataProvider with an injected fake session."""
    provider = object.__new__(MarketDataProvider)
    provider._api_key = "test-key"
    provider._session = fake_session
    provider._calls_per_minute = 100
    provider._call_times = []
    return provider


# ── Protocol conformance ─────────────────────────────────────────────


class TestProtocolConformance:
    def test_implements_data_provider(self):
        provider = _make_provider(FakeSession())
        assert isinstance(provider, DataProvider)

    def test_implements_options_data_provider(self):
        provider = _make_provider(FakeSession())
        assert isinstance(provider, OptionsDataProvider)

    def test_name(self):
        provider = _make_provider(FakeSession())
        assert provider.name == "marketdata"


# ── fetch_bars ───────────────────────────────────────────────────────


class TestFetchBars:
    def test_returns_ohlcv_dataframe(self):
        session = FakeSession()
        session.responses["candles"] = FakeResponse({
            "s": "ok",
            "t": [1704067200, 1704153600, 1704240000],
            "o": [100.0, 103.0, 106.0],
            "h": [105.0, 107.0, 108.0],
            "l": [99.0, 102.0, 104.0],
            "c": [103.0, 106.0, 107.5],
            "v": [1000000, 1200000, 900000],
        })
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert len(df) == 3
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df["close"].iloc[-1] == 107.5

    def test_empty_when_no_data(self):
        session = FakeSession()
        session.responses["candles"] = FakeResponse({"s": "no_data"})
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert df.empty


# ── fetch_option_chain ───────────────────────────────────────────────


class TestFetchOptionChain:
    def test_returns_grouped_chains(self):
        session = FakeSession()
        session.responses["options/chain"] = FakeResponse({
            "s": "ok",
            "optionSymbol": ["AAPL240119C190", "AAPL240119P190", "AAPL240216C200"],
            "strike": [190.0, 190.0, 200.0],
            "expiration": ["2024-01-19", "2024-01-19", "2024-02-16"],
            "side": ["call", "put", "call"],
            "bid": [5.0, 3.0, 7.0],
            "ask": [5.5, 3.5, 7.5],
            "last": [5.25, 3.25, 7.25],
            "volume": [100, 50, 200],
            "openInterest": [1000, 500, 2000],
            "iv": [0.25, 0.28, 0.22],
            "inTheMoney": [True, False, False],
        })
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert len(chains) == 2
        assert chains[0].expiration == date(2024, 1, 19)
        assert len(chains[0].calls) == 1
        assert len(chains[0].puts) == 1
        assert chains[1].expiration == date(2024, 2, 16)
        assert chains[1].calls[0].implied_volatility == 0.22

    def test_empty_on_no_data(self):
        session = FakeSession()
        session.responses["options/chain"] = FakeResponse({"s": "no_data"})
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert chains == []


# ── fetch_current_price ──────────────────────────────────────────────


class TestFetchCurrentPrice:
    def test_returns_price(self):
        session = FakeSession()
        session.responses["quotes"] = FakeResponse({
            "s": "ok",
            "last": [195.50],
        })
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 195.50

    def test_returns_zero_on_error(self):
        session = FakeSession()

        def raise_error(*args, **kwargs):
            raise Exception("API error")

        session.get = raise_error
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 0.0


# ── Constructor ───────────────────────────────────────────────────────


class TestConstructor:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("MARKETDATA_API_KEY", raising=False)
        with pytest.raises(ValueError, match="MarketData API key required"):
            MarketDataProvider()
