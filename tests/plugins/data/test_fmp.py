"""Tests for the FMP data provider plugin."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument
from trading.plugins.data.base import DataProvider, DiscoveryProvider
from trading.plugins.data.fmp import FMPProvider


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
        self.last_url: str = ""
        self.last_params: dict = {}

    def get(self, url: str, params=None, timeout=None):
        self.last_url = url
        self.last_params = params or {}
        for key, resp in self.responses.items():
            if key in url:
                return resp
        return FakeResponse([])


def _make_provider(fake_session: FakeSession) -> FMPProvider:
    """Build an FMPProvider with an injected fake session."""
    provider = object.__new__(FMPProvider)
    provider._api_key = "test-key"
    provider._session = fake_session
    provider._calls_per_minute = 300
    provider._call_times = []
    return provider


# ── Protocol conformance ─────────────────────────────────────────────


class TestProtocolConformance:
    def test_implements_data_provider(self):
        provider = _make_provider(FakeSession())
        assert isinstance(provider, DataProvider)

    def test_implements_discovery_provider(self):
        provider = _make_provider(FakeSession())
        assert isinstance(provider, DiscoveryProvider)

    def test_name(self):
        provider = _make_provider(FakeSession())
        assert provider.name == "fmp"


# ── fetch_bars ───────────────────────────────────────────────────────


class TestFetchBars:
    def test_returns_ohlcv_dataframe(self):
        session = FakeSession()
        session.responses["historical-price-full"] = FakeResponse({
            "symbol": "AAPL",
            "historical": [
                {"date": "2024-01-01", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000000},
                {"date": "2024-01-02", "open": 103, "high": 107, "low": 102, "close": 106, "volume": 1200000},
                {"date": "2024-01-03", "open": 106, "high": 108, "low": 104, "close": 107.5, "volume": 900000},
            ],
        })
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert len(df) == 3
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df["close"].iloc[-1] == 107.5

    def test_empty_when_no_data(self):
        session = FakeSession()
        session.responses["historical-price-full"] = FakeResponse({"historical": []})
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        df = provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 1, 3))

        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_passes_date_params(self):
        session = FakeSession()
        session.responses["historical-price-full"] = FakeResponse({"historical": []})
        provider = _make_provider(session)
        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

        provider.fetch_bars(inst, date(2024, 1, 1), date(2024, 6, 15))

        assert session.last_params["from"] == "2024-01-01"
        assert session.last_params["to"] == "2024-06-15"


# ── list_universe ─────────────────────────────────────────────────────


class TestListUniverse:
    def test_forex_majors_hardcoded(self):
        provider = _make_provider(FakeSession())

        symbols = provider.list_universe("forex_majors")

        assert "EUR/USD" in symbols
        assert len(symbols) == 7

    def test_sp500_uses_api(self):
        session = FakeSession()
        session.responses["sp500_constituent"] = FakeResponse([
            {"symbol": "AAPL"}, {"symbol": "MSFT"}, {"symbol": "GOOG"},
        ])
        provider = _make_provider(session)

        symbols = provider.list_universe("sp500")

        assert symbols == ["AAPL", "MSFT", "GOOG"]

    def test_nasdaq100_uses_api(self):
        session = FakeSession()
        session.responses["nasdaq_constituent"] = FakeResponse([
            {"symbol": "NVDA"}, {"symbol": "META"},
        ])
        provider = _make_provider(session)

        symbols = provider.list_universe("nasdaq100")

        assert symbols == ["NVDA", "META"]

    def test_unknown_universe_returns_empty(self):
        provider = _make_provider(FakeSession())

        symbols = provider.list_universe("unknown_universe")

        assert symbols == []


# ── get_movers ────────────────────────────────────────────────────────


class TestGetMovers:
    def test_returns_movers(self):
        session = FakeSession()
        session.responses["gainers"] = FakeResponse([
            {"symbol": "AAPL", "changesPercentage": 5.2, "price": 190.50, "volume": 123456},
            {"symbol": "TSLA", "changesPercentage": 3.1, "price": 250.00, "volume": 654321},
        ])
        provider = _make_provider(session)

        movers = provider.get_movers("gainers", limit=10)

        assert len(movers) == 2
        assert movers[0]["symbol"] == "AAPL"
        assert movers[0]["change_pct"] == 5.2
        assert movers[0]["price"] == 190.50

    def test_respects_limit(self):
        session = FakeSession()
        session.responses["gainers"] = FakeResponse([
            {"symbol": f"SYM{i}", "changesPercentage": float(i), "price": float(i * 10), "volume": i * 1000}
            for i in range(30)
        ])
        provider = _make_provider(session)

        movers = provider.get_movers("gainers", limit=5)

        assert len(movers) == 5

    def test_empty_on_error(self):
        session = FakeSession()

        def raise_error(*args, **kwargs):
            raise Exception("API error")

        session.get = raise_error
        provider = _make_provider(session)

        movers = provider.get_movers("gainers")

        assert movers == []


# ── Constructor ───────────────────────────────────────────────────────


class TestConstructor:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("FMP_API_KEY", raising=False)
        with pytest.raises(ValueError, match="FMP API key required"):
            FMPProvider()
