"""Tests for the momentum / trend-following strategy."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from trading.core.models import AssetClass, Direction, Instrument
from trading.plugins.strategies.base import Strategy
from trading.plugins.strategies.momentum import MomentumStrategy


@pytest.fixture
def strategy():
    return MomentumStrategy(short_window=10, long_window=50)


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def make_trending_up_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with a clear uptrend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    close = np.linspace(180, 210, n_days) + np.random.default_rng(42).normal(0, 0.5, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


def make_trending_down_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with a clear downtrend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    close = np.linspace(210, 170, n_days) + np.random.default_rng(42).normal(0, 0.5, n_days)
    return pd.DataFrame(
        {
            "open": close + 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


def make_flat_bars(n_days: int = 80) -> pd.DataFrame:
    """Create synthetic price data with no clear trend."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    close = 190 + np.random.default_rng(42).normal(0, 1.0, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.3,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.default_rng(42).integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


class TestMomentumStrategy:
    def test_satisfies_protocol(self, strategy):
        assert isinstance(strategy, Strategy)

    def test_name(self, strategy):
        assert strategy.name == "momentum"

    def test_uptrend_generates_long_signal(self, strategy, aapl):
        bars = make_trending_up_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.LONG
        assert signals[0].conviction > 0.5
        assert signals[0].strategy_name == "momentum"
        assert "AAPL" in signals[0].rationale

    def test_downtrend_generates_short_or_close_signal(self, strategy, aapl):
        bars = make_trending_down_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction in (Direction.SHORT, Direction.CLOSE)
        assert signals[0].conviction > 0.3

    def test_flat_market_low_conviction(self, strategy, aapl):
        bars = make_flat_bars()
        signals = strategy.generate_signals(aapl, bars)
        if len(signals) > 0:
            assert signals[0].conviction < 0.5

    def test_insufficient_data_returns_empty(self, strategy, aapl):
        bars = make_trending_up_bars(n_days=5)
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_rationale_is_plain_english(self, strategy, aapl):
        bars = make_trending_up_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        rationale = signals[0].rationale
        assert len(rationale) > 20
        assert any(word in rationale.lower() for word in ["price", "trend", "above", "average", "moving"])
