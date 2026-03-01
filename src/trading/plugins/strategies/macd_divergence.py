"""MACD Divergence strategy plugin.

Detects price-vs-indicator divergences for reversal signals:
- Bullish divergence: price makes lower lows, MACD makes higher lows → LONG
- Bearish divergence: price makes higher highs, MACD makes lower highs → CLOSE
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal


class MACDDivergenceStrategy:
    """MACD divergence detection for reversal signals."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        short_window: int | None = None,
        long_window: int | None = None,
    ) -> None:
        # short_window maps to fast_period, long_window maps to slow_period
        if short_window is not None:
            fast_period = short_window
        if long_window is not None:
            slow_period = long_window
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    @property
    def name(self) -> str:
        return "macd_divergence"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        min_bars = self.slow_period + self.signal_period + 20
        if len(bars) < min_bars:
            return []

        close = bars["close"]
        volume = bars["volume"]

        # MACD indicators
        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        # Look at the last 20 bars for divergence detection
        window = 20
        recent_close = close.iloc[-window:].values
        recent_macd = macd_line.iloc[-window:].values

        # Find local extremes (minima and maxima) using a 5-bar window
        local_min_idx = self._find_local_extremes(recent_close, kind="min")
        local_max_idx = self._find_local_extremes(recent_close, kind="max")

        conviction = 0.0
        rationale_parts = []
        direction = None

        # Bullish divergence: price lower low, MACD higher low
        if len(local_min_idx) >= 2:
            i1, i2 = local_min_idx[-2], local_min_idx[-1]
            price_lower_low = recent_close[i2] < recent_close[i1]
            macd_higher_low = recent_macd[i2] > recent_macd[i1]

            if price_lower_low and macd_higher_low:
                direction = Direction.LONG

                # Divergence magnitude — how much do price and MACD disagree?
                price_drop = (recent_close[i1] - recent_close[i2]) / recent_close[i1]
                macd_rise = recent_macd[i2] - recent_macd[i1]
                div_score = min(abs(price_drop) * 5 + abs(macd_rise) * 10, 0.35)
                conviction += div_score
                rationale_parts.append(
                    f"{instrument.symbol} shows bullish divergence — "
                    f"price made a lower low but MACD is rising, "
                    f"suggesting selling pressure is weakening"
                )

        # Bearish divergence: price higher high, MACD lower high
        if direction is None and len(local_max_idx) >= 2:
            i1, i2 = local_max_idx[-2], local_max_idx[-1]
            price_higher_high = recent_close[i2] > recent_close[i1]
            macd_lower_high = recent_macd[i2] < recent_macd[i1]

            if price_higher_high and macd_lower_high:
                direction = Direction.CLOSE

                price_rise = (recent_close[i2] - recent_close[i1]) / recent_close[i1]
                macd_drop = recent_macd[i1] - recent_macd[i2]
                div_score = min(abs(price_rise) * 5 + abs(macd_drop) * 10, 0.35)
                conviction += div_score
                rationale_parts.append(
                    f"{instrument.symbol} shows bearish divergence — "
                    f"price made a higher high but MACD is falling, "
                    f"suggesting buying momentum is fading"
                )

        if direction is None:
            return []

        # Histogram direction confirming reversal (up to 0.20)
        hist_vals = histogram.iloc[-3:].values
        if direction == Direction.LONG and hist_vals[-1] > hist_vals[-2]:
            conviction += 0.20
            rationale_parts.append(
                "MACD histogram is turning upward, confirming momentum shift"
            )
        elif direction == Direction.LONG and hist_vals[-1] > hist_vals[-3]:
            conviction += 0.10
            rationale_parts.append("MACD histogram is starting to flatten")
        elif direction == Direction.CLOSE and hist_vals[-1] < hist_vals[-2]:
            conviction += 0.20
            rationale_parts.append(
                "MACD histogram is turning downward, confirming momentum shift"
            )
        elif direction == Direction.CLOSE and hist_vals[-1] < hist_vals[-3]:
            conviction += 0.10
            rationale_parts.append("MACD histogram is starting to flatten")

        # Volume confirmation (up to 0.20)
        avg_volume = volume.rolling(window=20).mean()
        latest_volume = float(volume.iloc[-1])
        latest_avg_vol = (
            float(avg_volume.iloc[-1])
            if not np.isnan(avg_volume.iloc[-1])
            else latest_volume
        )
        volume_ratio = latest_volume / latest_avg_vol if latest_avg_vol > 0 else 1.0

        if volume_ratio > 1.5:
            conviction += 0.20
            rationale_parts.append(
                f"Volume is {volume_ratio:.1f}x average, confirming the reversal signal"
            )
        elif volume_ratio > 1.0:
            conviction += 0.10
            rationale_parts.append(f"Volume is near average ({volume_ratio:.1f}x)")
        else:
            conviction += 0.05

        # MACD crossover alignment (up to 0.15)
        latest_macd = float(macd_line.iloc[-1])
        latest_signal = float(signal_line.iloc[-1])
        prev_macd = float(macd_line.iloc[-2])
        prev_signal = float(signal_line.iloc[-2])

        if direction == Direction.LONG and latest_macd > latest_signal and prev_macd <= prev_signal:
            conviction += 0.15
            rationale_parts.append(
                "MACD just crossed above the signal line — a classic buy trigger"
            )
        elif direction == Direction.LONG and latest_macd > latest_signal:
            conviction += 0.08
        elif direction == Direction.CLOSE and latest_macd < latest_signal and prev_macd >= prev_signal:
            conviction += 0.15
            rationale_parts.append(
                "MACD just crossed below the signal line — a classic sell trigger"
            )
        elif direction == Direction.CLOSE and latest_macd < latest_signal:
            conviction += 0.08

        conviction = round(min(conviction, 1.0), 2)
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

    @staticmethod
    def _find_local_extremes(
        values: np.ndarray, kind: str = "min", window: int = 5
    ) -> list[int]:
        """Find indices of local minima or maxima using a rolling window."""
        half = window // 2
        extremes = []
        for i in range(half, len(values) - half):
            segment = values[i - half : i + half + 1]
            if kind == "min" and values[i] == segment.min():
                extremes.append(i)
            elif kind == "max" and values[i] == segment.max():
                extremes.append(i)
        return extremes
