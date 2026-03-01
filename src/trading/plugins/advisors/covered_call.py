"""CoveredCallAdvisor — suggests covered call plays for positions with >= 100 shares."""

from __future__ import annotations

from datetime import date

from trading.core.models import OptionChain, OptionContract, Play, PlayType, Position


class CoveredCallAdvisor:
    """Recommends selling covered calls on positions with at least 100 shares."""

    @property
    def name(self) -> str:
        return "covered_call"

    def advise(
        self,
        position: Position,
        bars: object,
        option_chains: list[OptionChain],
        current_price: float,
    ) -> list[Play]:
        if position.total_quantity < 100:
            return []

        num_contracts = position.total_quantity // 100
        today = date.today()
        candidates = self._find_candidates(option_chains, current_price, today)

        if not candidates:
            return []

        # Score and pick the best candidate
        scored = sorted(candidates, key=lambda c: self._score(c, current_price, today), reverse=True)
        best = scored[0]

        premium = round(best.mid_price * 100 * num_contracts, 2)
        upside_to_strike = max(0, best.strike - current_price)
        max_profit = round(premium + upside_to_strike * 100 * num_contracts, 2)
        breakeven = round(position.average_cost - best.mid_price, 2)

        # Tax-lot awareness
        tax_notes = []
        for lot in position.tax_lots:
            if not lot.is_long_term(today):
                days_left = lot.days_to_long_term(today)
                tax_notes.append(
                    f"Lot {lot.purchase_date} ({lot.quantity} shares): "
                    f"if assigned, triggers short-term gain. "
                    f"{days_left} days to long-term"
                )
        tax_note = "; ".join(tax_notes) if tax_notes else None

        dte = (best.expiration - today).days
        annualized_yield = (best.mid_price / current_price) * (365 / max(dte, 1)) * 100
        symbol = position.instrument.symbol

        return [
            Play(
                position=position,
                play_type=PlayType.COVERED_CALL,
                title=f"Sell {num_contracts} covered call{'s' if num_contracts > 1 else ''} on {symbol}",
                rationale=(
                    f"Sell ${best.strike:.0f} calls expiring {best.expiration} "
                    f"({dte} DTE) for ~${best.mid_price:.2f}/contract. "
                    f"Annualized yield: {annualized_yield:.1f}%. "
                    f"OI: {best.open_interest:,}"
                ),
                conviction=min(self._score(best, current_price, today), 1.0),
                option_contract=best,
                contracts=num_contracts,
                premium=premium,
                max_profit=max_profit,
                breakeven=breakeven,
                tax_note=tax_note,
                playbook=(
                    f"1. Open your broker account\n"
                    f"2. Navigate to {symbol} options chain\n"
                    f"3. Select expiration: {best.expiration}\n"
                    f"4. Sell to Open {num_contracts} contract{'s' if num_contracts > 1 else ''} "
                    f"of {symbol} ${best.strike:.0f} Call\n"
                    f"5. Limit price: ${best.mid_price:.2f} (mid of ${best.bid:.2f}-${best.ask:.2f})\n"
                    f"6. Total premium: ~${premium:.2f}\n"
                    f"7. Max profit: ${max_profit:.2f} (premium + upside to strike)\n"
                    f"8. Breakeven: ${breakeven:.2f}"
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
        for chain in option_chains:
            dte = (chain.expiration - today).days
            if not (20 <= dte <= 60):
                continue
            for call in chain.calls:
                if (
                    call.strike > current_price
                    and call.bid > 0.50
                    and not call.in_the_money
                ):
                    candidates.append(call)
        return candidates

    def _score(
        self, contract: OptionContract, current_price: float, today: date
    ) -> float:
        dte = (contract.expiration - today).days
        if dte <= 0:
            return 0.0

        premium_yield = (contract.mid_price / current_price) * (365 / dte)
        distance_otm = (contract.strike - current_price) / current_price
        oi_score = min(contract.open_interest / 1000, 1.0)

        # Weighted score: premium yield is most important, then OTM distance, then OI
        score = premium_yield * 0.5 + distance_otm * 0.3 + oi_score * 0.2
        return min(max(score, 0.0), 1.0)
