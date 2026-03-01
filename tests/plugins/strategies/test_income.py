"""Tests for the income (premium-selling) strategy."""

import numpy as np
import pandas as pd
import pytest

from trading.core.models import AssetClass, Direction, Instrument
from trading.plugins.strategies.base import Strategy
from trading.plugins.strategies.income import IncomeStrategy


@pytest.fixture
def strategy():
    return IncomeStrategy()


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def make_high_vol_bars(n_days: int = 80) -> pd.DataFrame:
    """Stock with elevated volatility and high volume — good income candidate."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    # Stable price with wide daily ranges (high ATR)
    base = 190 + rng.normal(0, 0.5, n_days)
    daily_swing = rng.uniform(3, 7, n_days)  # Wide intraday range
    return pd.DataFrame(
        {
            "open": base,
            "high": base + daily_swing,
            "low": base - daily_swing,
            "close": base + rng.normal(0, 0.5, n_days),
            "volume": rng.integers(2_000_000, 5_000_000, n_days),
        },
        index=dates,
    )


def make_low_vol_bars(n_days: int = 80) -> pd.DataFrame:
    """Stock with very low volatility — poor income candidate."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    base = 190 + rng.normal(0, 0.1, n_days)
    return pd.DataFrame(
        {
            "open": base,
            "high": base + 0.1,
            "low": base - 0.1,
            "close": base,
            "volume": rng.integers(2_000_000, 5_000_000, n_days),
        },
        index=dates,
    )


def make_illiquid_bars(n_days: int = 80) -> pd.DataFrame:
    """Stock with high volatility but very low volume — too illiquid."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    base = 190 + rng.normal(0, 0.5, n_days)
    daily_swing = rng.uniform(3, 7, n_days)
    return pd.DataFrame(
        {
            "open": base,
            "high": base + daily_swing,
            "low": base - daily_swing,
            "close": base + rng.normal(0, 0.5, n_days),
            "volume": rng.integers(10_000, 50_000, n_days),  # Very low volume
        },
        index=dates,
    )


class TestIncomeStrategy:
    def test_satisfies_protocol(self, strategy):
        assert isinstance(strategy, Strategy)

    def test_name(self, strategy):
        assert strategy.name == "income"

    def test_high_vol_generates_long_signal(self, strategy, aapl):
        bars = make_high_vol_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.LONG
        assert signals[0].conviction > 0.3
        assert signals[0].strategy_name == "income"

    def test_low_vol_no_signal(self, strategy, aapl):
        bars = make_low_vol_bars()
        signals = strategy.generate_signals(aapl, bars)
        # Low vol stocks are filtered out
        assert signals == []

    def test_illiquid_no_signal(self, strategy, aapl):
        bars = make_illiquid_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_insufficient_data_returns_empty(self, strategy, aapl):
        bars = make_high_vol_bars(n_days=10)
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_conviction_bounded_zero_to_one(self, strategy, aapl):
        bars = make_high_vol_bars()
        signals = strategy.generate_signals(aapl, bars)
        if signals:
            assert 0.0 <= signals[0].conviction <= 1.0

    def test_rationale_mentions_volatility(self, strategy, aapl):
        bars = make_high_vol_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        rationale = signals[0].rationale.lower()
        assert "volatility" in rationale or "atr" in rationale

    def test_rationale_mentions_volume(self, strategy, aapl):
        bars = make_high_vol_bars()
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert "volume" in signals[0].rationale.lower()
