"""Tests for the Polygon.io data provider plugin."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument
from trading.plugins.data.base import DataProvider, DiscoveryProvider, OptionsDataProvider
from trading.plugins.data.polygon import PolygonProvider


# ── Fake Polygon client ──────────────────────────────────────────────


class FakeAgg:
    """Mimics a polygon Agg result."""

    def __init__(self, timestamp_ms: int, o: float, h: float, l: float, c: float, v: int):
        self.timestamp = timestamp_ms
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.volume = v


class FakeOptionsContract:
    def __init__(self, ticker: str, strike: float, exp: str, contract_type: str):
        self.ticker = ticker
        self.strike_price = strike
        self.expiration_date = exp
        self.contract_type = contract_type


class FakeTrade:
    def __init__(self, price: float):
        self.price = price


class FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker


class FakeSnapshotItem:
    def __init__(self, ticker: str, change_pct: float, price: float, volume: int):
        self.ticker = ticker
        self.todays_change_percent = change_pct
        self.day = SimpleNamespace(close=price, volume=volume)


class FakeRESTClient:
    """Hand-built fake of polygon.RESTClient for unit tests."""

    def __init__(self, api_key: str = "test"):
        self.api_key = api_key
        self._aggs: list[FakeAgg] = []
        self._contracts: list[FakeOptionsContract] = []
        self._last_trade: FakeTrade | None = None
        self._tickers: list[FakeTicker] = []
        self._movers: list[FakeSnapshotItem] = []

    def list_aggs(self, **kwargs):
        return iter(self._aggs)

    def list_options_contracts(self, **kwargs):
        return iter(self._contracts)

    def get_snapshot_option(self, underlying, option_ticker):
        return None  # Pricing is best-effort

    def get_last_trade(self, ticker: str):
        if self._last_trade is None:
            raise Exception("No trade data")
        return self._last_trade

    def list_tickers(self, **kwargs):
        return iter(self._tickers)

    def get_snapshot_direction(self, market, direction, **kwargs):
        return self._movers


def _make_provider(fake_client: FakeRESTClient) -> PolygonProvider:
    """Build a PolygonProvider with an injected fake client."""
    # Bypass __init__ to avoid needing a real API key
    provider = object.__new__(PolygonProvider)
    provider._client = fake_client
    provider._calls_per_minute = 5
    provider._call_times: list[float] = []
    return provider


# ── Protocol conformance ─────────────────────────────────────────────


class TestProtocolConformance:
    def test_implements_data_provider(self):
        provider = _make_provider(FakeRESTClient())
        assert isinstance(provider, DataProvider)

    def test_implements_options_data_provider(self):
        provider = _make_provider(FakeRESTClient())
        assert isinstance(provider, OptionsDataProvider)

    def test_implements_discovery_provider(self):
        provider = _make_provider(FakeRESTClient())
        assert isinstance(provider, DiscoveryProvider)

    def test_name(self):
        provider = _make_provider(FakeRESTClient())
        assert provider.name == "polygon"


# ── fetch_bars ───────────────────────────────────────────────────────


class TestFetchBars:
    def test_returns_ohlcv_dataframe(self):
        client = FakeRESTClient()
        # 3 days of data (timestamps in ms)
        client._aggs = [
            FakeAgg(1704067200000, 100.0, 105.0, 99.0, 103.0, 1000000),  # 2024-01-01
            FakeAgg(1704153600000, 103.0, 107.0, 102.0, 106.0, 1200000),  # 2024-01-02
            FakeAgg(1704240000000, 106.0, 108.0, 104.0, 107.5, 900000),   # 2024-01-03
        ]
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert len(df) == 3
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df["close"].iloc[-1] == 107.5

    def test_empty_when_no_data(self):
        client = FakeRESTClient()
        client._aggs = []
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_forex_uses_c_prefix(self):
        client = FakeRESTClient()
        captured_kwargs = {}

        original_list_aggs = client.list_aggs

        def capture_list_aggs(**kwargs):
            captured_kwargs.update(kwargs)
            return original_list_aggs(**kwargs)

        client.list_aggs = capture_list_aggs
        provider = _make_provider(client)
        inst = Instrument(symbol="EUR/USD", asset_class=AssetClass.FOREX)

        provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert captured_kwargs["ticker"] == "C:EURUSD"


# ── fetch_current_price ──────────────────────────────────────────────


class TestFetchCurrentPrice:
    def test_returns_price(self):
        client = FakeRESTClient()
        client._last_trade = FakeTrade(195.50)
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 195.50

    def test_returns_zero_on_error(self):
        client = FakeRESTClient()
        client._last_trade = None  # Will raise
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        price = provider.fetch_current_price(inst)

        assert price == 0.0


# ── fetch_option_chain ───────────────────────────────────────────────


class TestFetchOptionChain:
    def test_returns_grouped_chains(self):
        client = FakeRESTClient()
        client._contracts = [
            FakeOptionsContract("O:AAPL240119C00190000", 190.0, "2024-01-19", "call"),
            FakeOptionsContract("O:AAPL240119P00190000", 190.0, "2024-01-19", "put"),
            FakeOptionsContract("O:AAPL240216C00200000", 200.0, "2024-02-16", "call"),
        ]
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert len(chains) == 2  # Two expirations
        assert chains[0].expiration == date(2024, 1, 19)
        assert len(chains[0].calls) == 1
        assert len(chains[0].puts) == 1
        assert chains[1].expiration == date(2024, 2, 16)
        assert len(chains[1].calls) == 1

    def test_empty_on_no_contracts(self):
        client = FakeRESTClient()
        client._contracts = []
        provider = _make_provider(client)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        chains = provider.fetch_option_chain(inst)

        assert chains == []


# ── list_universe ─────────────────────────────────────────────────────


class TestListUniverse:
    def test_forex_majors_hardcoded(self):
        provider = _make_provider(FakeRESTClient())

        symbols = provider.list_universe("forex_majors")

        assert "EUR/USD" in symbols
        assert "GBP/USD" in symbols
        assert len(symbols) == 7

    def test_sp500_uses_api(self):
        client = FakeRESTClient()
        client._tickers = [FakeTicker("AAPL"), FakeTicker("MSFT"), FakeTicker("GOOG")]
        provider = _make_provider(client)

        symbols = provider.list_universe("sp500")

        assert symbols == ["AAPL", "MSFT", "GOOG"]

    def test_unknown_universe_returns_empty(self):
        provider = _make_provider(FakeRESTClient())

        symbols = provider.list_universe("unknown_universe")

        assert symbols == []


# ── get_movers ────────────────────────────────────────────────────────


class TestGetMovers:
    def test_returns_movers(self):
        client = FakeRESTClient()
        client._movers = [
            FakeSnapshotItem("AAPL", 5.2, 190.50, 123456),
            FakeSnapshotItem("TSLA", 3.1, 250.00, 654321),
        ]
        provider = _make_provider(client)

        movers = provider.get_movers("gainers", limit=10)

        assert len(movers) == 2
        assert movers[0]["symbol"] == "AAPL"
        assert movers[0]["change_pct"] == 5.2
        assert movers[0]["price"] == 190.50
        assert movers[1]["symbol"] == "TSLA"

    def test_respects_limit(self):
        client = FakeRESTClient()
        client._movers = [
            FakeSnapshotItem(f"SYM{i}", float(i), float(i * 10), i * 1000)
            for i in range(30)
        ]
        provider = _make_provider(client)

        movers = provider.get_movers("gainers", limit=5)

        assert len(movers) == 5

    def test_empty_on_error(self):
        client = FakeRESTClient()

        def raise_error(*args, **kwargs):
            raise Exception("API error")

        client.get_snapshot_direction = raise_error
        provider = _make_provider(client)

        movers = provider.get_movers("gainers")

        assert movers == []


# ── Constructor ───────────────────────────────────────────────────────


class TestConstructor:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("POLYGON_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Polygon API key required"):
            PolygonProvider()
