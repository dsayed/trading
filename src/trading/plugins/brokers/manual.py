"""Manual broker plugin — generates Action Playbooks for the user to execute."""

from __future__ import annotations

from trading.core.models import Direction, Order

STRATEGY_EXPLANATIONS = {
    "momentum": "the price has been trending in this direction with strong follow-through",
    "mean_reversion": "the price has moved too far in one direction and is likely to snap back",
    "income": "this stock has the right conditions to generate income from options premiums",
}

CONFIDENCE_LABELS = {
    (0.0, 0.4): ("low", "This is a weaker signal — consider a smaller position or skip it."),
    (0.4, 0.6): ("moderate", "Decent opportunity, but not a slam dunk."),
    (0.6, 0.8): ("good", "Strong setup with multiple factors lining up."),
    (0.8, 1.01): ("high", "This is one of the stronger signals — most factors are in your favor."),
}


def _confidence_text(conviction: float) -> tuple[str, str]:
    for (lo, hi), (label, desc) in CONFIDENCE_LABELS.items():
        if lo <= conviction < hi:
            return label, desc
    return "moderate", ""


class ManualBroker:
    """Generates step-by-step Action Playbooks instead of executing trades."""

    @property
    def name(self) -> str:
        return "manual"

    def present_order(
        self,
        order: Order,
        current_price: float,
        conviction: float = 0.0,
        strategy_name: str = "",
    ) -> str:
        if order.direction in (Direction.LONG, Direction.SHORT):
            return self._buy_playbook(order, current_price, conviction, strategy_name)
        else:
            return self._sell_playbook(order, current_price, conviction, strategy_name)

    def _buy_playbook(
        self,
        order: Order,
        current_price: float,
        conviction: float,
        strategy_name: str,
    ) -> str:
        action = "Buy" if order.direction == Direction.LONG else "Short sell"
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price
        position_value = qty * limit
        stop = order.stop_price

        conf_label, conf_desc = _confidence_text(conviction)
        strategy_why = STRATEGY_EXPLANATIONS.get(
            strategy_name,
            "the analysis suggests this is a good entry point",
        )

        lines = [
            f"BOTTOM LINE",
            f"  {action} {qty} shares of {symbol} at ${limit:.2f} "
            f"(total: ${position_value:,.0f}).",
            f"  Why: {strategy_why.capitalize()}.",
            f"  Confidence: {conviction:.0%} ({conf_label}) — {conf_desc}",
            "",
        ]

        # Upside first
        lines.append("WHAT COULD GO RIGHT:")
        for pct, label in [(0.05, "5%"), (0.10, "10%"), (0.25, "25%")]:
            rise_price = limit * (1 + pct)
            gain = qty * limit * pct
            lines.append(
                f"  + If {symbol} rises {label} to ${rise_price:.2f}: "
                f"you make ~${gain:,.0f}"
            )

        # Downside
        lines.append("")
        lines.append("WHAT COULD GO WRONG:")
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
                f"  Your stop-loss at ${stop:.2f} limits the downside "
                f"to ~${stop_loss:,.0f}.",
            ])

        # Steps
        lines.extend([
            "",
            "HOW TO PLACE THIS TRADE:",
            f"  1. Open your broker -> Trade -> Stocks",
            f"  2. Enter: {action} {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f}",
            f"  5. Time in force: Good 'til Canceled (GTC)",
            f"  6. Review and submit",
        ])

        if stop:
            lines.extend([
                "",
                f"  Then set a stop-loss:",
                f"  Trade -> {symbol} -> Sell -> Stop order at ${stop:.2f}",
            ])

        return "\n".join(lines)

    def _sell_playbook(
        self,
        order: Order,
        current_price: float,
        conviction: float,
        strategy_name: str,
    ) -> str:
        symbol = order.instrument.symbol
        qty = order.quantity
        limit = order.limit_price or current_price
        proceeds = qty * limit

        conf_label, conf_desc = _confidence_text(conviction)
        strategy_why = STRATEGY_EXPLANATIONS.get(
            strategy_name,
            "the analysis suggests it's time to exit",
        )

        lines = [
            f"BOTTOM LINE",
            f"  Sell {qty} shares of {symbol} at ${limit:.2f} "
            f"(proceeds: ~${proceeds:,.0f}).",
            f"  Why: {strategy_why.capitalize()}.",
            f"  Confidence: {conviction:.0%} ({conf_label}) — {conf_desc}",
            "",
            "HOW TO PLACE THIS TRADE:",
            f"  1. Open your broker -> Trade -> Stocks",
            f"  2. Enter: Sell {qty} shares of {symbol}",
            f"  3. Order type: Limit",
            f"  4. Limit price: ${limit:.2f}",
            f"  5. Time in force: Day",
            f"  6. Review and submit",
        ]

        return "\n".join(lines)
