"""Broker protocol — all broker plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trading.core.models import Order


@runtime_checkable
class Broker(Protocol):
    @property
    def name(self) -> str: ...

    def present_order(
        self,
        order: Order,
        current_price: float,
        conviction: float = 0.0,
        strategy_name: str = "",
    ) -> str: ...
