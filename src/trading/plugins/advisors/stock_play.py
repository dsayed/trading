"""StockPlayAdvisor — suggests equity plays (stop-loss, trim, add, hold)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.core.models import Play, PlayType, Position


class StockPlayAdvisor:
    """Generates stock-only plays: stop-loss, trim, add, hold."""

    @property
    def name(self) -> str:
        return "stock_play"

    def advise(
        self,
        position: Position,
        bars: pd.DataFrame,
        option_chains: list,
        current_price: float,
    ) -> list[Play]:
        plays: list[Play] = []
        symbol = position.instrument.symbol

        # Always suggest a stop-loss
        stop_play = self._stop_loss_play(position, bars, current_price, symbol)
        if stop_play:
            plays.append(stop_play)

        # Trim if position is up significantly
        trim_play = self._trim_play(position, current_price, symbol)
        if trim_play:
            plays.append(trim_play)

        # Add if momentum is turning positive
        add_play = self._add_play(position, bars, current_price, symbol)
        if add_play:
            plays.append(add_play)

        # Hold as default when no strong signal
        if not plays:
            plays.append(self._hold_play(position, current_price, symbol))

        return plays

    def _stop_loss_play(
        self, position: Position, bars: pd.DataFrame, current_price: float, symbol: str
    ) -> Play | None:
        if len(bars) < 20:
            # Use percentage-based stop if not enough data
            stop_price = round(current_price * 0.95, 2)
            rationale = f"Set a 5% trailing stop to protect against downside"
        else:
            # Use recent low as support level
            recent_low = float(bars["low"].tail(20).min())
            stop_price = round(recent_low * 0.98, 2)  # 2% below recent support
            rationale = (
                f"Recent 20-day support is at ${recent_low:.2f}. "
                f"Setting stop 2% below at ${stop_price:.2f} to protect gains"
            )

        loss_per_share = current_price - stop_price
        max_loss = round(loss_per_share * position.total_quantity, 2)

        return Play(
            position=position,
            play_type=PlayType.STOP_LOSS,
            title=f"Set stop-loss on {symbol}",
            rationale=rationale,
            conviction=0.70,
            max_loss=max_loss,
            playbook=(
                f"1. Open your broker account\n"
                f"2. Navigate to {symbol} position\n"
                f"3. Place a STOP order at ${stop_price:.2f}\n"
                f"4. Quantity: {position.total_quantity} shares\n"
                f"5. Duration: Good 'Til Cancelled (GTC)\n"
                f"6. Max loss if triggered: ${max_loss:.2f}"
            ),
            advisor_name=self.name,
        )

    def _trim_play(
        self, position: Position, current_price: float, symbol: str
    ) -> Play | None:
        pnl_pct = (current_price - position.average_cost) / position.average_cost
        if pnl_pct <= 0.20:
            return None

        trim_qty = max(1, position.total_quantity // 4)  # Trim ~25%
        proceeds = round(trim_qty * current_price, 2)

        # Tax-lot awareness
        today = date.today()
        tax_notes = []
        for lot in position.tax_lots:
            if not lot.is_long_term(today):
                days_left = lot.days_to_long_term(today)
                tax_notes.append(
                    f"Lot purchased {lot.purchase_date} ({lot.quantity} shares): "
                    f"short-term gains, {days_left} days until long-term"
                )

        tax_note = "; ".join(tax_notes) if tax_notes else None

        return Play(
            position=position,
            play_type=PlayType.TRIM,
            title=f"Trim {symbol} — up {pnl_pct:.0%}",
            rationale=(
                f"Position is up {pnl_pct:.0%} from average cost of ${position.average_cost:.2f}. "
                f"Consider taking partial profits to reduce risk"
            ),
            conviction=min(0.50 + pnl_pct * 0.5, 0.90),
            max_profit=proceeds,
            tax_note=tax_note,
            playbook=(
                f"1. Open your broker account\n"
                f"2. Sell {trim_qty} shares of {symbol} at market\n"
                f"3. Expected proceeds: ~${proceeds:.2f}\n"
                f"4. Remaining position: {position.total_quantity - trim_qty} shares"
            ),
            advisor_name=self.name,
        )

    def _add_play(
        self, position: Position, bars: pd.DataFrame, current_price: float, symbol: str
    ) -> Play | None:
        if len(bars) < 50:
            return None

        close = bars["close"]
        sma_short = float(close.rolling(window=10).mean().iloc[-1])
        sma_long = float(close.rolling(window=50).mean().iloc[-1])

        rsi = self._calculate_rsi(close)
        latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

        # Only suggest adding if momentum is turning positive
        if sma_short <= sma_long or latest_rsi >= 70:
            return None

        conviction = 0.50
        if 50 < latest_rsi < 65:
            conviction += 0.15
        if sma_short > sma_long * 1.02:
            conviction += 0.15

        return Play(
            position=position,
            play_type=PlayType.ADD,
            title=f"Add to {symbol} position",
            rationale=(
                f"Momentum is turning positive: 10-day SMA (${sma_short:.2f}) "
                f"above 50-day SMA (${sma_long:.2f}), RSI at {latest_rsi:.0f}"
            ),
            conviction=min(conviction, 0.85),
            playbook=(
                f"1. Open your broker account\n"
                f"2. Buy additional shares of {symbol}\n"
                f"3. Current price: ${current_price:.2f}\n"
                f"4. Consider sizing based on your risk tolerance\n"
                f"5. Set a stop-loss after purchase"
            ),
            advisor_name=self.name,
        )

    def _hold_play(
        self, position: Position, current_price: float, symbol: str
    ) -> Play:
        pnl = position.unrealized_pnl(current_price)
        pnl_pct = (current_price - position.average_cost) / position.average_cost

        return Play(
            position=position,
            play_type=PlayType.HOLD,
            title=f"Hold {symbol}",
            rationale=(
                f"No strong signal to act. Current P&L: ${pnl:.2f} ({pnl_pct:+.1%}). "
                f"Continue monitoring"
            ),
            conviction=0.50,
            playbook=f"1. Continue holding {position.total_quantity} shares of {symbol}\n2. Monitor for changes in trend",
            advisor_name=self.name,
        )

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
