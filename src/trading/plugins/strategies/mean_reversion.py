"""Mean-reversion strategy plugin.

Generates signals when price is at statistical extremes:
- LONG when oversold (RSI < 30) AND near Bollinger Band lower bound
- CLOSE when overbought (RSI > 70) AND above Bollinger Band upper bound
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal


class MeanReversionStrategy:
    """Mean reversion using RSI + Bollinger Bands + volume confirmation."""

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        bb_proximity_pct: float = 2.0,
    ) -> None:
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_proximity_pct = bb_proximity_pct

    @property
    def name(self) -> str:
        return "mean_reversion"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        min_periods = max(self.bb_window, self.rsi_period) + 5
        if len(bars) < min_periods:
            return []

        close = bars["close"]
        volume = bars["volume"]

        # Calculate indicators
        rsi = self._calculate_rsi(close, self.rsi_period)
        bb_mid = close.rolling(window=self.bb_window).mean()
        bb_std = close.rolling(window=self.bb_window).std()
        bb_upper = bb_mid + self.bb_std * bb_std
        bb_lower = bb_mid - self.bb_std * bb_std

        avg_volume = volume.rolling(window=20).mean()

        latest_close = float(close.iloc[-1])
        latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
        latest_bb_upper = float(bb_upper.iloc[-1])
        latest_bb_lower = float(bb_lower.iloc[-1])
        latest_bb_mid = float(bb_mid.iloc[-1])
        latest_volume = float(volume.iloc[-1])
        latest_avg_volume = (
            float(avg_volume.iloc[-1])
            if not np.isnan(avg_volume.iloc[-1])
            else latest_volume
        )
        volume_ratio = latest_volume / latest_avg_volume if latest_avg_volume > 0 else 1.0

        # Distance from Bollinger Bands as percentage
        bb_range = latest_bb_upper - latest_bb_lower
        dist_to_lower_pct = (
            (latest_close - latest_bb_lower) / latest_bb_lower * 100
            if latest_bb_lower > 0
            else 99.0
        )
        dist_to_upper_pct = (
            (latest_bb_upper - latest_close) / latest_close * 100
            if latest_close > 0
            else 99.0
        )

        conviction = 0.0
        rationale_parts = []

        # Oversold — potential long entry
        is_oversold = latest_rsi < self.rsi_oversold
        near_lower_band = dist_to_lower_pct < self.bb_proximity_pct

        # Overbought — potential exit
        is_overbought = latest_rsi > self.rsi_overbought
        above_upper_band = latest_close > latest_bb_upper

        if is_oversold and near_lower_band:
            direction = Direction.LONG

            # RSI extremity: deeper oversold = higher conviction
            rsi_depth = (self.rsi_oversold - latest_rsi) / self.rsi_oversold
            conviction += min(rsi_depth * 0.5, 0.35)
            rationale_parts.append(
                f"{instrument.symbol} is oversold with RSI at {latest_rsi:.0f}, "
                f"suggesting a potential bounce"
            )

            # Bollinger Band proximity
            bb_score = max(0, (self.bb_proximity_pct - dist_to_lower_pct)) / self.bb_proximity_pct
            conviction += bb_score * 0.25
            rationale_parts.append(
                f"Price (${latest_close:.2f}) is near the lower Bollinger Band "
                f"(${latest_bb_lower:.2f}), {dist_to_lower_pct:.1f}% above it"
            )

            # Volume confirmation
            if volume_ratio > 1.5:
                conviction += 0.20
                rationale_parts.append(
                    f"High volume ({volume_ratio:.1f}x average) suggests capitulation selling"
                )
            elif volume_ratio > 1.0:
                conviction += 0.10
                rationale_parts.append(
                    f"Volume is {volume_ratio:.1f}x average"
                )
            else:
                conviction += 0.05

        elif is_overbought and above_upper_band:
            direction = Direction.CLOSE

            rsi_excess = (latest_rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
            conviction += min(rsi_excess * 0.4, 0.35)
            rationale_parts.append(
                f"{instrument.symbol} is overbought with RSI at {latest_rsi:.0f}, "
                f"suggesting a potential pullback"
            )

            pct_above_upper = (latest_close - latest_bb_upper) / latest_bb_upper * 100
            conviction += min(pct_above_upper / 5.0, 0.25)
            rationale_parts.append(
                f"Price (${latest_close:.2f}) is above the upper Bollinger Band "
                f"(${latest_bb_upper:.2f})"
            )

            if volume_ratio > 1.2:
                conviction += 0.15
                rationale_parts.append(
                    f"Heavy volume ({volume_ratio:.1f}x average) on the move up"
                )
            else:
                conviction += 0.05
        else:
            # No signal — price is in normal range
            return []

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
    def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
