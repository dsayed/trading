"""Momentum / trend-following strategy plugin.

Generates signals based on moving average crossovers, RSI, and volume confirmation.
Uses plain-English rationale for all signals.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal


class MomentumStrategy:
    """Momentum strategy using SMA crossover with RSI and volume confirmation."""

    def __init__(self, short_window: int = 10, long_window: int = 50) -> None:
        self.short_window = short_window
        self.long_window = long_window

    @property
    def name(self) -> str:
        return "momentum"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        if len(bars) < self.long_window:
            return []

        close = bars["close"]
        volume = bars["volume"]

        # Calculate indicators
        sma_short = close.rolling(window=self.short_window).mean()
        sma_long = close.rolling(window=self.long_window).mean()
        rsi = self._calculate_rsi(close, period=14)
        avg_volume = volume.rolling(window=20).mean()

        latest_close = float(close.iloc[-1])
        latest_sma_short = float(sma_short.iloc[-1])
        latest_sma_long = float(sma_long.iloc[-1])
        latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
        latest_volume = float(volume.iloc[-1])
        latest_avg_volume = float(avg_volume.iloc[-1]) if not np.isnan(avg_volume.iloc[-1]) else latest_volume
        volume_ratio = latest_volume / latest_avg_volume if latest_avg_volume > 0 else 1.0

        # Determine trend direction
        sma_cross_up = latest_sma_short > latest_sma_long
        price_above_long = latest_close > latest_sma_long
        pct_above_long = (latest_close - latest_sma_long) / latest_sma_long * 100

        # Calculate conviction (0-1) based on multiple factors
        conviction = 0.0
        rationale_parts = []

        if sma_cross_up and price_above_long:
            # Bullish
            direction = Direction.LONG

            cross_strength = min(abs(pct_above_long) / 5.0, 0.4)
            conviction += cross_strength
            rationale_parts.append(
                f"{instrument.symbol}'s price (${latest_close:.2f}) is trading "
                f"{abs(pct_above_long):.1f}% above its {self.long_window}-day moving average, "
                f"indicating an upward trend"
            )

            if 50 < latest_rsi < 70:
                conviction += 0.2
                rationale_parts.append(
                    f"Buying momentum is healthy (RSI at {latest_rsi:.0f} — "
                    f"strong but not overbought)"
                )
            elif latest_rsi >= 70:
                conviction += 0.05
                rationale_parts.append(
                    f"Caution: buying momentum is very high (RSI at {latest_rsi:.0f} — "
                    f"approaching overbought territory)"
                )
            else:
                conviction += 0.1
                rationale_parts.append(
                    f"Buying momentum is moderate (RSI at {latest_rsi:.0f})"
                )

            if volume_ratio > 1.2:
                conviction += 0.2
                rationale_parts.append(
                    f"Trading volume is {volume_ratio:.1f}x higher than average, "
                    f"confirming buyer interest"
                )
            elif volume_ratio > 0.8:
                conviction += 0.1
                rationale_parts.append("Trading volume is near average")
            else:
                rationale_parts.append(
                    f"Trading volume is below average ({volume_ratio:.1f}x), "
                    f"suggesting weak conviction in the move"
                )

        elif not sma_cross_up or not price_above_long:
            # Bearish
            direction = Direction.CLOSE

            cross_strength = min(abs(pct_above_long) / 5.0, 0.4)
            conviction += cross_strength
            rationale_parts.append(
                f"{instrument.symbol}'s price (${latest_close:.2f}) is trading "
                f"{abs(pct_above_long):.1f}% below its {self.long_window}-day moving average, "
                f"indicating a downward trend"
            )

            if latest_rsi < 30:
                conviction += 0.15
                rationale_parts.append(
                    f"Selling pressure is extreme (RSI at {latest_rsi:.0f} — oversold)"
                )
            elif latest_rsi < 50:
                conviction += 0.2
                rationale_parts.append(
                    f"Selling pressure is present (RSI at {latest_rsi:.0f})"
                )
            else:
                conviction += 0.05
                rationale_parts.append(
                    f"Selling pressure is light (RSI at {latest_rsi:.0f})"
                )

            if volume_ratio > 1.2:
                conviction += 0.2
                rationale_parts.append(
                    f"Heavy volume ({volume_ratio:.1f}x average) confirms selling pressure"
                )
            else:
                conviction += 0.05

        conviction = min(conviction, 1.0)

        rationale = ". ".join(rationale_parts) + "."

        timestamp = bars.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        return [
            Signal(
                instrument=instrument,
                direction=direction,
                conviction=round(conviction, 2),
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
