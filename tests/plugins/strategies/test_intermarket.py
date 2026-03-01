"""Tests for the Intermarket / Global Macro strategy."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from trading.core.models import AssetClass, Direction, Instrument
from trading.plugins.strategies.base import Strategy
from trading.plugins.strategies.intermarket import IntermarketStrategy


@pytest.fixture
def aapl():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def _make_bars(start_price: float, end_price: float, n_days: int = 40) -> pd.DataFrame:
    """Create simple trending bars from start_price to end_price."""
    dates = pd.date_range(start="2026-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    close = np.linspace(start_price, end_price, n_days) + rng.normal(0, 0.1, n_days)
    return pd.DataFrame(
        {
            "open": close - 0.3,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": rng.integers(10_000_000, 50_000_000, n_days),
        },
        index=dates,
    )


class FakeDataProvider:
    """Fake data provider that returns preset bars for benchmark symbols."""

    def __init__(self, benchmark_bars: dict[str, pd.DataFrame]) -> None:
        self._bars = benchmark_bars
        self.call_count = 0

    def get_bars(self, instrument: Instrument, lookback: int) -> pd.DataFrame | None:
        self.call_count += 1
        return self._bars.get(instrument.symbol)


def _risk_on_benchmarks() -> dict[str, pd.DataFrame]:
    """SPY up, UUP down, TLT down, GLD flat → Risk-On."""
    return {
        "SPY": _make_bars(400, 420),   # up
        "UUP": _make_bars(28, 26),     # down
        "TLT": _make_bars(100, 95),    # down
        "GLD": _make_bars(180, 182),   # flat/slight up
    }


def _risk_off_benchmarks() -> dict[str, pd.DataFrame]:
    """SPY down, UUP up, TLT up, GLD up → Risk-Off."""
    return {
        "SPY": _make_bars(420, 390),   # down
        "UUP": _make_bars(26, 29),     # up
        "TLT": _make_bars(95, 110),    # up
        "GLD": _make_bars(180, 195),   # up
    }


class TestIntermarketStrategy:
    def test_satisfies_protocol(self):
        strategy = IntermarketStrategy(data_provider=FakeDataProvider({}))
        assert isinstance(strategy, Strategy)

    def test_name(self):
        strategy = IntermarketStrategy(data_provider=FakeDataProvider({}))
        assert strategy.name == "intermarket"

    def test_risk_on_regime_generates_long(self, aapl):
        provider = FakeDataProvider(_risk_on_benchmarks())
        strategy = IntermarketStrategy(data_provider=provider)
        # Stock trending up in a risk-on regime → LONG
        bars = _make_bars(180, 200, n_days=40)
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.LONG
        assert signals[0].conviction >= 0.30
        assert "Risk-On" in signals[0].rationale

    def test_risk_off_regime_generates_close(self, aapl):
        provider = FakeDataProvider(_risk_off_benchmarks())
        strategy = IntermarketStrategy(data_provider=provider)
        # Stock trending down in a risk-off regime → CLOSE
        bars = _make_bars(200, 180, n_days=40)
        signals = strategy.generate_signals(aapl, bars)
        assert len(signals) == 1
        assert signals[0].direction == Direction.CLOSE
        assert signals[0].conviction >= 0.30

    def test_caches_benchmark_bars(self, aapl):
        provider = FakeDataProvider(_risk_on_benchmarks())
        strategy = IntermarketStrategy(data_provider=provider)
        bars = _make_bars(180, 200, n_days=40)

        # First call loads benchmarks
        strategy.generate_signals(aapl, bars)
        first_count = provider.call_count

        # Second call should NOT re-fetch benchmarks
        strategy.generate_signals(aapl, bars)
        assert provider.call_count == first_count

    def test_empty_bars_returns_empty(self, aapl):
        provider = FakeDataProvider(_risk_on_benchmarks())
        strategy = IntermarketStrategy(data_provider=provider)
        bars = _make_bars(180, 200, n_days=5)  # too few bars
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_no_data_provider_returns_empty(self, aapl):
        strategy = IntermarketStrategy(data_provider=None)
        bars = _make_bars(180, 200, n_days=40)
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_benchmark_failure_returns_empty(self, aapl):
        """If benchmarks can't load, return empty."""

        class FailingProvider:
            def get_bars(self, instrument, lookback):
                raise ConnectionError("API down")

        strategy = IntermarketStrategy(data_provider=FailingProvider())
        bars = _make_bars(180, 200, n_days=40)
        signals = strategy.generate_signals(aapl, bars)
        assert signals == []

    def test_holding_period_overrides(self):
        """short_window maps to sma_period."""
        s = IntermarketStrategy(short_window=10, data_provider=None)
        assert s.sma_period == 10

    def test_rationale_includes_regime(self, aapl):
        provider = FakeDataProvider(_risk_on_benchmarks())
        strategy = IntermarketStrategy(data_provider=provider)
        bars = _make_bars(180, 200, n_days=40)
        signals = strategy.generate_signals(aapl, bars)
        if signals:
            assert any(
                word in signals[0].rationale.lower()
                for word in ["regime", "macro", "risk-on", "risk-off"]
            )
