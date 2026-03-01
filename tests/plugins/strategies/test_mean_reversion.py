"""Tests for the mean reversion strategy."""

import numpy as np
import pandas as pd
import pytest

from trading.core.models import AssetClass, Direction, Instrument
from trading.plugins.strategies.base import Strategy
from trading.plugins.strategies.mean_reversion import MeanReversionStrategy


@pytest.fixture
def strategy():
    return MeanReversionStrategy()


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def make_oversold_bars(n_days: int = 80) -> pd.DataFrame:
    """Price drops sharply to near lower Bollinger Band with low RSI."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    # Start flat, then drop sharply in last 20 days
    close = np.concatenate([
        190 + rng.normal(0, 0.5, n_days - 20),
        np.linspace(190, 175, 20) + rng.normal(0, 0.3, 20),
    ])
    return pd.DataFrame(
        {
            "open": close + 0.3,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": rng.integers(40_000_000, 80_000_000, n_days),
        },
        index=dates,
    )


def make_overbought_bars(n_days: int = 80) -> pd.DataFrame:
    """Price surges above upper Bollinger Band with high RSI."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    # Tight range for most of the period, then a sudden 5-day explosive move.
    # This keeps the Bollinger Band tight while RSI spikes to ~97.
    close = np.concatenate([
        190 + rng.normal(0, 0.3, n_days - 5),
        [195, 200, 206, 213, 221],
    ])
    return pd.DataFrame(
        {
            "open": close - 0.3,
            "high": close + 0.5,
            "low": close - 0.3,
            "close": close,
            "volume": rng.integers(40_000_000, 80_000_000, n_days),
        },
        index=dates,
    )


def make_normal_range_bars(n_days: int = 80) -> pd.DataFrame:
    """Price in normal range — no signal expected."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    close = 190 + rng.normal(0, 0.5, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": rng.integers(40_000_000, 60_000_000, n_days),
        },
        index=dates,
    )


class TestMeanReversionStrategy:
    def test_satisfies_protocol(self, strategy):
        assert isinstance(strategy, Strategy)

    def test_name(self, strategy):
        assert strategy.name == "mean_reversion"

    def test_oversold_generates_long_signal(self, strategy, aapl):
        bars = make_oversold_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.LONG
        assert signals[0].conviction > 0.2
        assert signals[0].strategy_name == "mean_reversion"
        assert "AAPL" in signals[0].rationale

    def test_overbought_generates_close_signal(self, strategy, aapl):
        bars = make_overbought_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.CLOSE
        assert signals[0].conviction > 0.1

    def test_normal_range_no_signal(self, strategy, aapl):
        bars = make_normal_range_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_insufficient_data_returns_empty(self, strategy, aapl):
        # Need at least bb_window + rsi_period + 5 days (~39)
        dates = pd.date_range(start="2026-01-01", periods=10, freq="B")
        rng = np.random.default_rng(42)
        close = 190 + rng.normal(0, 0.5, 10)
        bars = pd.DataFrame(
            {
                "open": close - 0.3,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": rng.integers(40_000_000, 60_000_000, 10),
            },
            index=dates,
        )
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_conviction_bounded_zero_to_one(self, strategy, aapl):
        bars = make_oversold_bars()
        signals = strategy.generate_signals(aapl, bars)
        if signals:
            assert 0.0 <= signals[0].conviction <= 1.0

    def test_rationale_mentions_rsi_and_bollinger(self, strategy, aapl):
        bars = make_oversold_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        rationale = signals[0].rationale.lower()
        assert "rsi" in rationale
        assert "bollinger" in rationale
