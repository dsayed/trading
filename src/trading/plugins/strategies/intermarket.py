"""Intermarket / Global Macro strategy plugin.

Uses cross-asset trends (SPY, dollar, bonds, gold) as context for equity signals.
Determines the macro regime and favors stocks aligned with that regime.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal

# Benchmark ETFs used for regime detection
BENCHMARKS = {
    "SPY": "S&P 500",
    "UUP": "US Dollar",
    "TLT": "Treasury Bonds",
    "GLD": "Gold",
}

# Macro regime definitions based on benchmark trends
# Each regime maps to: (spy_up, uup_up, tlt_up, gld_up) → name
REGIME_NAMES = {
    "risk_on": "Risk-On",
    "risk_off": "Risk-Off",
    "reflation": "Reflation",
    "deflation": "Deflation",
    "mixed": "Mixed",
}


class IntermarketStrategy:
    """Global macro strategy using cross-asset regime detection."""

    def __init__(
        self,
        sma_period: int = 20,
        data_provider: Any = None,
        short_window: int | None = None,
        long_window: int | None = None,
    ) -> None:
        if short_window is not None:
            sma_period = short_window
        self.sma_period = sma_period
        self._data_provider = data_provider
        self._benchmarks: dict[str, pd.DataFrame] | None = None

    @property
    def name(self) -> str:
        return "intermarket"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        if len(bars) < self.sma_period + 5:
            return []

        if self._data_provider is None:
            return []

        # Lazy-load and cache benchmarks on first call
        if self._benchmarks is None:
            self._benchmarks = self._load_benchmarks()

        if not self._benchmarks:
            return []

        # Determine macro regime from benchmarks
        regime, regime_details = self._detect_regime()

        # Analyze the stock itself
        close = bars["close"]
        sma = close.rolling(window=self.sma_period).mean()
        latest_close = float(close.iloc[-1])
        latest_sma = float(sma.iloc[-1])
        stock_trending_up = latest_close > latest_sma

        # Calculate relative strength vs SPY
        spy_bars = self._benchmarks.get("SPY")
        rel_strength = 0.0
        if spy_bars is not None and len(bars) >= self.sma_period and len(spy_bars) >= self.sma_period:
            stock_return = (float(close.iloc[-1]) - float(close.iloc[-self.sma_period])) / float(close.iloc[-self.sma_period])
            spy_close = spy_bars["close"]
            spy_return = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-self.sma_period])) / float(spy_close.iloc[-self.sma_period])
            rel_strength = stock_return - spy_return

        # Determine direction based on regime + stock alignment
        conviction = 0.0
        rationale_parts = []
        direction = None

        is_bullish_regime = regime in ("risk_on", "reflation")
        is_bearish_regime = regime in ("risk_off", "deflation")

        if is_bullish_regime and stock_trending_up:
            direction = Direction.LONG
        elif is_bearish_regime and not stock_trending_up:
            direction = Direction.CLOSE
        elif is_bullish_regime and not stock_trending_up:
            # Bullish macro but stock lagging — weak long
            direction = Direction.LONG
        elif is_bearish_regime and stock_trending_up:
            # Bearish macro but stock strong — no signal
            return []
        else:
            # Mixed regime
            if stock_trending_up and rel_strength > 0.02:
                direction = Direction.LONG
            elif not stock_trending_up and rel_strength < -0.02:
                direction = Direction.CLOSE
            else:
                return []

        # --- Score components ---

        # 1. Macro alignment (40%)
        if is_bullish_regime and stock_trending_up:
            macro_score = 0.40
            rationale_parts.append(
                f"Macro regime is {REGIME_NAMES[regime]} ({regime_details}), "
                f"and {instrument.symbol} is trending above its {self.sma_period}-day average — "
                f"aligned with the bullish macro backdrop"
            )
        elif is_bearish_regime and not stock_trending_up:
            macro_score = 0.40
            rationale_parts.append(
                f"Macro regime is {REGIME_NAMES[regime]} ({regime_details}), "
                f"and {instrument.symbol} is trending below its {self.sma_period}-day average — "
                f"confirming macro weakness"
            )
        elif is_bullish_regime:
            macro_score = 0.15
            rationale_parts.append(
                f"Macro regime is {REGIME_NAMES[regime]} ({regime_details}), "
                f"but {instrument.symbol} hasn't joined the rally yet"
            )
        else:
            macro_score = 0.20
            rationale_parts.append(
                f"Macro regime is {REGIME_NAMES.get(regime, 'Mixed')} ({regime_details})"
            )
        conviction += macro_score

        # 2. Relative strength vs SPY (30%)
        if direction == Direction.LONG and rel_strength > 0.03:
            rs_score = 0.30
            rationale_parts.append(
                f"Outperforming SPY by {rel_strength:.1%} over {self.sma_period} days — "
                f"strong relative strength"
            )
        elif direction == Direction.LONG and rel_strength > 0:
            rs_score = 0.15
            rationale_parts.append(
                f"Slightly outperforming SPY ({rel_strength:+.1%})"
            )
        elif direction == Direction.CLOSE and rel_strength < -0.03:
            rs_score = 0.30
            rationale_parts.append(
                f"Underperforming SPY by {abs(rel_strength):.1%} — weak relative strength"
            )
        elif direction == Direction.CLOSE and rel_strength < 0:
            rs_score = 0.15
            rationale_parts.append(
                f"Slightly underperforming SPY ({rel_strength:+.1%})"
            )
        else:
            rs_score = 0.05
        conviction += rs_score

        # 3. Own trend quality (30%)
        pct_from_sma = (latest_close - latest_sma) / latest_sma
        if direction == Direction.LONG and pct_from_sma > 0.02:
            trend_score = min(pct_from_sma * 5, 0.30)
            rationale_parts.append(
                f"Price is {pct_from_sma:.1%} above its {self.sma_period}-day SMA — solid uptrend"
            )
        elif direction == Direction.CLOSE and pct_from_sma < -0.02:
            trend_score = min(abs(pct_from_sma) * 5, 0.30)
            rationale_parts.append(
                f"Price is {abs(pct_from_sma):.1%} below its {self.sma_period}-day SMA — in a downtrend"
            )
        else:
            trend_score = 0.05
        conviction += trend_score

        conviction = round(min(conviction, 1.0), 2)

        # Only emit signal if conviction exceeds threshold
        if conviction < 0.30:
            return []

        rationale = ". ".join(rationale_parts) + "."

        timestamp = bars.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        return [
            Signal(
                instrument=instrument,
                direction=direction,
                conviction=conviction,
                rationale=rationale,
                strategy_name=self.name,
                timestamp=timestamp,
            )
        ]

    def _load_benchmarks(self) -> dict[str, pd.DataFrame]:
        """Fetch benchmark ETF bars. Gracefully skips failures."""
        benchmarks: dict[str, pd.DataFrame] = {}
        lookback = self.sma_period + 10

        for symbol in BENCHMARKS:
            try:
                bm_instrument = Instrument(
                    symbol=symbol, asset_class="equity"
                )
                bm_bars = self._data_provider.get_bars(
                    bm_instrument, lookback
                )
                if bm_bars is not None and len(bm_bars) >= self.sma_period:
                    benchmarks[symbol] = bm_bars
            except Exception:
                # Graceful degradation — skip this benchmark
                continue

        return benchmarks

    def _detect_regime(self) -> tuple[str, str]:
        """Determine macro regime from benchmark trends.

        Returns (regime_key, human_readable_details).
        """
        trends: dict[str, bool] = {}
        details: list[str] = []

        for symbol, label in BENCHMARKS.items():
            bm = self._benchmarks.get(symbol) if self._benchmarks else None
            if bm is None or len(bm) < self.sma_period:
                continue
            close = bm["close"]
            sma = close.rolling(window=self.sma_period).mean()
            is_up = float(close.iloc[-1]) > float(sma.iloc[-1])
            trends[symbol] = is_up
            arrow = "up" if is_up else "down"
            details.append(f"{label} {arrow}")

        spy_up = trends.get("SPY")
        uup_up = trends.get("UUP")
        tlt_up = trends.get("TLT")
        gld_up = trends.get("GLD")

        detail_str = ", ".join(details) if details else "no benchmark data"

        # Classify regime
        if spy_up and not uup_up and not tlt_up:
            return "risk_on", detail_str
        if not spy_up and uup_up and tlt_up:
            return "risk_off", detail_str
        if spy_up and not uup_up and not tlt_up and gld_up:
            return "reflation", detail_str
        if not spy_up and uup_up and tlt_up and not gld_up:
            return "deflation", detail_str

        # Fallback: use SPY as primary indicator
        if spy_up:
            return "risk_on", detail_str
        if spy_up is False:
            return "risk_off", detail_str

        return "mixed", detail_str
