"""Manual broker plugin — generates Action Playbooks for the user to execute."""

from __future__ import annotations

from trading.core.models import Direction, Order


class ManualBroker:
    """Generates step-by-step Action Playbooks instead of executing trades."""

    @property
    def name(self) -> str:
        return "manual"

    def present_order(self, order: Order, current_price: float) -> str:
        if order.direction in (Direction.LONG, Direction.SHORT):
            return self._buy_playbook(order, current_price)
        else:
            return self._sell_playbook(order, current_price)

    def _buy_playbook(self, order: Order, current_price: float) -> str:
        action = "Buy" if order.direction == Direction.LONG else "Short sell"
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price
        position_value = qty * limit
        stop = order.stop_price

        lines = [
            f"{'=' * 55}",
            f"  ACTION PLAYBOOK: {action} {symbol}",
            f"{'=' * 55}",
            "",
            "WHAT TO DO:",
            f"  1. Open your broker -> Trade -> Stocks",
            f"  2. Enter: {action} {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f} (current price is ${current_price:.2f})",
            f"  5. Time in force: Good 'til Canceled (GTC)",
            f"  6. Review and submit",
            "",
            "WHY:",
            f"  {order.rationale}",
            "",
            "WHAT COULD GO WRONG:",
        ]

        for pct, label in [(0.05, "5%"), (0.10, "10%"), (0.25, "25%")]:
            drop_price = limit * (1 - pct)
            loss = qty * limit * pct
            lines.append(
                f"  - If {symbol} drops {label} to ${drop_price:.2f}: "
                f"you lose ~${loss:,.0f}"
            )

        if stop:
            stop_loss = qty * (limit - stop)
            lines.extend([
                "",
                "STOP-LOSS:",
                f"  Set a stop-loss order at ${stop:.2f} to limit your downside "
                f"to ~${stop_loss:,.0f}.",
                f"  In your broker: Trade -> {symbol} -> Sell -> Stop order at ${stop:.2f}",
            ])

        return "\n".join(lines)

    def _sell_playbook(self, order: Order, current_price: float) -> str:
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price

        lines = [
            f"{'=' * 55}",
            f"  ACTION PLAYBOOK: Sell {symbol}",
            f"{'=' * 55}",
            "",
            "WHAT TO DO:",
            f"  1. Open your broker -> Trade -> Stocks",
            f"  2. Enter: Sell {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f} (current price is ${current_price:.2f})",
            f"  5. Time in force: Day",
            f"  6. Review and submit",
            "",
            "WHY:",
            f"  {order.rationale}",
        ]

        return "\n".join(lines)
