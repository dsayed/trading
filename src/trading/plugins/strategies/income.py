"""Income strategy plugin — screens for premium-selling candidates.

Identifies stocks with high implied volatility relative to historical norms,
suitable for covered call or cash-secured put strategies.

When options data is not available, uses ATR-based volatility proxy.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from trading.core.models import Direction, Instrument, Signal


class IncomeStrategy:
    """Screens for premium-selling candidates using IV rank or ATR proxy."""

    def __init__(
        self,
        atr_period: int = 14,
        atr_high_pct: float = 3.0,
        vol_lookback: int = 60,
    ) -> None:
        self.atr_period = atr_period
        self.atr_high_pct = atr_high_pct
        self.vol_lookback = vol_lookback

    @property
    def name(self) -> str:
        return "income"

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]:
        min_periods = max(self.vol_lookback, self.atr_period) + 5
        if len(bars) < min_periods:
            return []

        close = bars["close"]
        high = bars["high"]
        low = bars["low"]
        volume = bars["volume"]

        # ATR as volatility proxy (when IV data isn't available from bars)
        atr = self._calculate_atr(high, low, close, self.atr_period)
        latest_close = float(close.iloc[-1])
        latest_atr = float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else 0.0
        atr_pct = (latest_atr / latest_close * 100) if latest_close > 0 else 0.0

        # Historical volatility rank (ATR percentile over lookback)
        atr_pct_series = atr / close * 100
        recent_atr_pcts = atr_pct_series.iloc[-self.vol_lookback:]
        atr_percentile = (
            float((recent_atr_pcts < atr_pct).sum() / len(recent_atr_pcts))
            if len(recent_atr_pcts) > 0
            else 0.5
        )

        # Volume assessment — higher volume = more liquid options
        avg_volume = volume.rolling(window=20).mean()
        latest_volume = float(volume.iloc[-1])
        latest_avg_vol = (
            float(avg_volume.iloc[-1])
            if not np.isnan(avg_volume.iloc[-1])
            else latest_volume
        )

        # Trend stability — prefer range-bound or mildly trending stocks
        rsi = self._calculate_rsi(close, 14)
        latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

        # Score the opportunity
        conviction = 0.0
        rationale_parts = []

        # IV proxy score: higher ATR percentile = higher premium opportunity
        if atr_percentile > 0.7:
            iv_score = min((atr_percentile - 0.5) * 0.6, 0.35)
            conviction += iv_score
            rationale_parts.append(
                f"{instrument.symbol} has elevated volatility "
                f"(ATR {atr_pct:.1f}% of price, {atr_percentile:.0%} percentile), "
                f"suggesting rich option premiums"
            )
        elif atr_percentile > 0.5:
            conviction += 0.10
            rationale_parts.append(
                f"Volatility is moderate ({atr_percentile:.0%} percentile)"
            )
        else:
            # Low vol — not a great income candidate
            return []

        # Volume score: liquid names are preferred
        if latest_avg_vol > 1_000_000:
            conviction += 0.20
            rationale_parts.append(
                f"Highly liquid with {latest_avg_vol / 1e6:.1f}M avg daily volume"
            )
        elif latest_avg_vol > 500_000:
            conviction += 0.15
            rationale_parts.append(
                f"Reasonably liquid with {latest_avg_vol / 1e6:.1f}M avg daily volume"
            )
        elif latest_avg_vol > 100_000:
            conviction += 0.10
            rationale_parts.append("Adequate volume for options trading")
        else:
            # Too illiquid for options
            return []

        # Trend stability: RSI near 50 = more predictable for income
        rsi_stability = 1.0 - abs(latest_rsi - 50) / 50
        stability_score = rsi_stability * 0.20
        conviction += stability_score
        if 40 <= latest_rsi <= 60:
            rationale_parts.append(
                f"Price trend is stable (RSI {latest_rsi:.0f}), "
                f"good for covered call or cash-secured put"
            )
        elif latest_rsi > 60:
            rationale_parts.append(
                f"Upward bias (RSI {latest_rsi:.0f}) favors covered call writing"
            )
        else:
            rationale_parts.append(
                f"Downward bias (RSI {latest_rsi:.0f}) favors cash-secured put writing"
            )

        # ATR gives a target premium
        rationale_parts.append(
            f"Expected move: ~${latest_atr:.2f}/day (ATR), "
            f"suggesting premium target of ${latest_atr * 5:.2f}+ for 30-day options"
        )

        conviction = round(min(conviction, 1.0), 2)
        rationale = ". ".join(rationale_parts) + "."

        timestamp = bars.index[-1]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        return [
            Signal(
                instrument=instrument,
                direction=Direction.LONG,
                conviction=conviction,
                rationale=rationale,
                strategy_name=self.name,
                timestamp=timestamp,
            )
        ]

    @staticmethod
    def _calculate_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Average True Range — measures daily volatility."""
        prev_close = close.shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
