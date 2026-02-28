"""Fixed stake risk manager — sizes positions based on a fixed dollar stake."""

from __future__ import annotations

import math

from trading.core.models import Direction, Order, OrderType, Position, Signal


class FixedStakeRiskManager:
    """Sizes positions as a percentage of a fixed stake amount."""

    def __init__(
        self,
        stake: float = 10_000,
        max_position_pct: float = 0.40,
        stop_loss_pct: float = 0.05,
    ) -> None:
        self.stake = stake
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct

    @property
    def name(self) -> str:
        return "fixed_stake"

    def evaluate(
        self,
        signal: Signal,
        current_price: float,
        positions: list[Position],
        cash: float,
    ) -> Order | None:
        if signal.direction == Direction.CLOSE:
            return self._handle_close(signal, current_price, positions)
        return self._handle_entry(signal, current_price, cash)

    def _handle_entry(self, signal: Signal, current_price: float, cash: float) -> Order | None:
        if cash <= 0 or current_price <= 0:
            return None

        max_dollars = self.stake * self.max_position_pct
        available = min(max_dollars, cash)
        quantity = math.floor(available / current_price)

        if quantity <= 0:
            return None

        position_value = quantity * current_price
        stop_price = round(current_price * (1 - self.stop_loss_pct), 2)
        max_loss = quantity * current_price * self.stop_loss_pct

        rationale = (
            f"Position size: {quantity} shares at ${current_price:.2f} "
            f"= ${position_value:,.0f} "
            f"({position_value / self.stake * 100:.0f}% of ${self.stake:,.0f} stake). "
            f"Stop-loss at ${stop_price:.2f} limits downside to ${max_loss:,.0f}."
        )

        return Order(
            instrument=signal.instrument,
            direction=signal.direction,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=current_price,
            stop_price=stop_price,
            rationale=rationale,
        )

    def _handle_close(self, signal: Signal, current_price: float, positions: list[Position]) -> Order | None:
        matching = [p for p in positions if p.instrument == signal.instrument]
        if not matching:
            return None

        position = matching[0]
        quantity = position.total_quantity
        position_value = quantity * current_price
        pnl = position.unrealized_pnl(current_price)

        rationale = (
            f"Close {quantity} shares of {signal.instrument.symbol} at ${current_price:.2f} "
            f"= ${position_value:,.0f}. "
            f"Unrealized P&L: ${pnl:+,.0f}."
        )

        return Order(
            instrument=signal.instrument,
            direction=Direction.CLOSE,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=current_price,
            rationale=rationale,
        )
