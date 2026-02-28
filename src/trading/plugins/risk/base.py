"""RiskManager protocol — all risk management plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trading.core.models import Order, Position, Signal


@runtime_checkable
class RiskManager(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(
        self,
        signal: Signal,
        current_price: float,
        positions: list[Position],
        cash: float,
    ) -> Order | None: ...
