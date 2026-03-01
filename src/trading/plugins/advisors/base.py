"""PositionAdvisor protocol — advisor plugins recommend plays for positions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import OptionChain, Play, Position


@runtime_checkable
class PositionAdvisor(Protocol):
    @property
    def name(self) -> str: ...

    def advise(
        self,
        position: Position,
        bars: pd.DataFrame,
        option_chains: list[OptionChain],
        current_price: float,
    ) -> list[Play]: ...
