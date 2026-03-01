"""Tests for StockPlayAdvisor using hand-built fake data."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trading.core.models import (
    AssetClass,
    Instrument,
    PlayType,
    Position,
    TaxLot,
)
from trading.plugins.advisors.base import PositionAdvisor
from trading.plugins.advisors.stock_play import StockPlayAdvisor


@pytest.fixture
def advisor():
    return StockPlayAdvisor()


@pytest.fixture
def instrument():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def _make_uptrend_bars(periods=80) -> pd.DataFrame:
    """Bars with clear uptrend: 10-day SMA above 50-day SMA, with noise to keep RSI moderate."""
    dates = pd.date_range(start="2026-01-01", periods=periods, freq="B")
    rng = np.random.default_rng(42)
    # Gradual uptrend with daily noise so RSI doesn't peg at 100
    trend = np.linspace(180, 210, periods)
    noise = rng.normal(0, 1.5, periods)
    close = trend + noise
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [50_000_000] * periods,
        },
        index=dates,
    )


def _make_flat_bars(periods=80) -> pd.DataFrame:
    """Bars with flat/sideways movement."""
    dates = pd.date_range(start="2026-01-01", periods=periods, freq="B")
    close = np.full(periods, 190.0) + np.random.default_rng(42).uniform(-0.5, 0.5, periods)
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": [30_000_000] * periods,
        },
        index=dates,
    )


class TestStockPlayAdvisor:
    def test_satisfies_protocol(self, advisor):
        assert isinstance(advisor, PositionAdvisor)

    def test_name(self, advisor):
        assert advisor.name == "stock_play"

    def test_always_returns_plays(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_flat_bars()
        plays = advisor.advise(pos, bars, [], 190.0)
        assert len(plays) > 0

    def test_stop_loss_always_present_with_enough_data(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        plays = advisor.advise(pos, bars, [], 220.0)
        stop_plays = [p for p in plays if p.play_type == PlayType.STOP_LOSS]
        assert len(stop_plays) == 1

    def test_trim_when_up_significantly(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=150.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        current_price = 200.0  # up 33%
        plays = advisor.advise(pos, bars, [], current_price)
        trim_plays = [p for p in plays if p.play_type == PlayType.TRIM]
        assert len(trim_plays) == 1
        assert "33%" in trim_plays[0].title

    def test_no_trim_when_small_gain(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=185.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        plays = advisor.advise(pos, bars, [], 190.0)  # up only ~2.7%
        trim_plays = [p for p in plays if p.play_type == PlayType.TRIM]
        assert len(trim_plays) == 0

    def test_trim_has_tax_note_for_short_term(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=150.0, purchase_date=date(2026, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        plays = advisor.advise(pos, bars, [], 200.0)
        trim_plays = [p for p in plays if p.play_type == PlayType.TRIM]
        assert len(trim_plays) == 1
        assert trim_plays[0].tax_note is not None
        assert "short-term" in trim_plays[0].tax_note

    def test_add_on_uptrend(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=190.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        plays = advisor.advise(pos, bars, [], 220.0)
        add_plays = [p for p in plays if p.play_type == PlayType.ADD]
        assert len(add_plays) == 1

    def test_hold_when_no_strong_signal(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=190.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_flat_bars(periods=30)  # too few bars for add signal
        plays = advisor.advise(pos, bars, [], 190.0)
        # Should have at least one play (stop-loss or hold)
        assert len(plays) >= 1

    def test_playbook_has_steps(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        bars = _make_uptrend_bars()
        plays = advisor.advise(pos, bars, [], 220.0)
        for play in plays:
            assert "1." in play.playbook
            assert play.advisor_name == "stock_play"
