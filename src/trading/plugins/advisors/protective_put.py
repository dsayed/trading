"""ProtectivePutAdvisor — suggests buying protective puts to hedge downside."""

from __future__ import annotations

from datetime import date

from trading.core.models import OptionChain, OptionContract, Play, PlayType, Position


class ProtectivePutAdvisor:
    """Recommends buying protective puts to limit downside risk."""

    @property
    def name(self) -> str:
        return "protective_put"

    def advise(
        self,
        position: Position,
        bars: object,
        option_chains: list[OptionChain],
        current_price: float,
    ) -> list[Play]:
        today = date.today()
        num_contracts = max(1, position.total_quantity // 100)
        candidates = self._find_candidates(option_chains, current_price, today)

        if not candidates:
            return []

        # Pick the best put: closest to 10% OTM with reasonable cost
        scored = sorted(
            candidates,
            key=lambda c: self._score(c, current_price, position, today),
            reverse=True,
        )
        best = scored[0]

        cost = round(best.mid_price * 100 * num_contracts, 2)
        position_value = round(current_price * position.total_quantity, 2)
        cost_pct = cost / position_value * 100 if position_value > 0 else 0
        max_loss = round((current_price - best.strike) * position.total_quantity + cost, 2)

        # Tax-lot awareness: if lots approaching long-term, puts protect through transition
        tax_notes = []
        for lot in position.tax_lots:
            if not lot.is_long_term(today):
                days_left = lot.days_to_long_term(today)
                dte = (best.expiration - today).days
                if days_left <= dte:
                    tax_notes.append(
                        f"Lot {lot.purchase_date} ({lot.quantity} shares): "
                        f"put protects through long-term transition in {days_left} days"
                    )
                else:
                    tax_notes.append(
                        f"Lot {lot.purchase_date} ({lot.quantity} shares): "
                        f"{days_left} days to long-term status"
                    )
        tax_note = "; ".join(tax_notes) if tax_notes else None

        dte = (best.expiration - today).days
        symbol = position.instrument.symbol

        return [
            Play(
                position=position,
                play_type=PlayType.PROTECTIVE_PUT,
                title=f"Buy protective put{'s' if num_contracts > 1 else ''} on {symbol}",
                rationale=(
                    f"Buy ${best.strike:.0f} puts expiring {best.expiration} "
                    f"({dte} DTE) for ~${best.mid_price:.2f}/contract. "
                    f"Cost of protection: {cost_pct:.1f}% of position value. "
                    f"Caps max loss at ${max_loss:.2f}"
                ),
                conviction=min(self._score(best, current_price, position, today), 1.0),
                option_contract=best,
                contracts=num_contracts,
                premium=cost,
                max_loss=max_loss,
                breakeven=round(current_price + best.mid_price, 2),
                tax_note=tax_note,
                playbook=(
                    f"1. Open your broker account\n"
                    f"2. Navigate to {symbol} options chain\n"
                    f"3. Select expiration: {best.expiration}\n"
                    f"4. Buy to Open {num_contracts} contract{'s' if num_contracts > 1 else ''} "
                    f"of {symbol} ${best.strike:.0f} Put\n"
                    f"5. Limit price: ${best.mid_price:.2f} (mid of ${best.bid:.2f}-${best.ask:.2f})\n"
                    f"6. Total cost: ~${cost:.2f}\n"
                    f"7. Max loss with protection: ${max_loss:.2f}\n"
                    f"8. Protection expires: {best.expiration}"
                ),
                advisor_name=self.name,
            )
        ]

    def _find_candidates(
        self,
        option_chains: list[OptionChain],
        current_price: float,
        today: date,
    ) -> list[OptionContract]:
        candidates = []
        lower_bound = current_price * 0.85  # 15% below
        upper_bound = current_price * 0.95  # 5% below
        for chain in option_chains:
            dte = (chain.expiration - today).days
            if dte < 20:
                continue
            for put in chain.puts:
                if (
                    lower_bound <= put.strike <= upper_bound
                    and put.ask > 0
                    and not put.in_the_money
                ):
                    candidates.append(put)
        return candidates

    def _score(
        self,
        contract: OptionContract,
        current_price: float,
        position: Position,
        today: date,
    ) -> float:
        dte = (contract.expiration - today).days
        if dte <= 0:
            return 0.0

        # Prefer puts ~10% OTM (sweet spot between cost and protection)
        distance_otm = (current_price - contract.strike) / current_price
        distance_score = 1.0 - abs(distance_otm - 0.10) * 5  # peaks at 10% OTM

        # Lower cost is better
        cost_pct = contract.mid_price / current_price
        cost_score = max(0, 1.0 - cost_pct * 20)

        # More OI = better liquidity
        oi_score = min(contract.open_interest / 1000, 1.0)

        score = distance_score * 0.4 + cost_score * 0.3 + oi_score * 0.3
        return min(max(score, 0.0), 1.0)
