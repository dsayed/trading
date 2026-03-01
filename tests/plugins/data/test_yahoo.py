"""Tests for Yahoo Finance data provider."""
from datetime import date, datetime

import pandas as pd
import pytest

from trading.core.models import AssetClass, Instrument, OptionChain
from trading.plugins.data.base import DataProvider, OptionsDataProvider
from trading.plugins.data.yahoo import YahooFinanceProvider


@pytest.fixture
def provider():
    return YahooFinanceProvider()


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, exchange="NASDAQ")


class TestYahooFinanceProvider:
    def test_satisfies_protocol(self, provider):
        assert isinstance(provider, DataProvider)

    def test_name(self, provider):
        assert provider.name == "yahoo"

    @pytest.mark.slow
    def test_fetch_bars_real(self, provider, aapl):
        """Integration test — hits real Yahoo Finance API."""
        bars = provider.fetch_bars(aapl, start=date(2025, 1, 2), end=date(2025, 1, 10))
        assert isinstance(bars, pd.DataFrame)
        assert len(bars) > 0
        assert "open" in bars.columns
        assert "high" in bars.columns
        assert "low" in bars.columns
        assert "close" in bars.columns
        assert "volume" in bars.columns

    def test_fetch_bars_returns_correct_columns(self, provider, aapl, monkeypatch):
        """Unit test with mocked data."""
        mock_data = pd.DataFrame(
            {
                "Open": [185.0],
                "High": [187.0],
                "Low": [184.0],
                "Close": [186.0],
                "Volume": [50000000],
            },
            index=pd.DatetimeIndex([datetime(2026, 2, 28)]),
        )

        def mock_download(*args, **kwargs):
            return mock_data

        monkeypatch.setattr("trading.plugins.data.yahoo.yf.download", mock_download)
        bars = provider.fetch_bars(aapl, start=date(2026, 2, 1), end=date(2026, 2, 28))
        assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
        assert bars.iloc[0]["close"] == 186.0

    def test_satisfies_options_protocol(self, provider):
        assert isinstance(provider, OptionsDataProvider)

    @pytest.mark.slow
    def test_fetch_option_chain_real(self, provider, aapl):
        """Integration test — hits real Yahoo Finance API for option chains."""
        chains = provider.fetch_option_chain(aapl)
        assert isinstance(chains, list)
        assert len(chains) > 0
        chain = chains[0]
        assert isinstance(chain, OptionChain)
        assert len(chain.calls) > 0
        assert len(chain.puts) > 0
        assert chain.calls[0].option_type == "call"
        assert chain.puts[0].option_type == "put"

    @pytest.mark.slow
    def test_fetch_current_price_real(self, provider, aapl):
        """Integration test — hits real Yahoo Finance API for current price."""
        price = provider.fetch_current_price(aapl)
        assert isinstance(price, float)
        assert price > 0
