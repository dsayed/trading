"""Strategy protocol — all strategy plugins implement this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument, Signal


@runtime_checkable
class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def generate_signals(
        self, instrument: Instrument, bars: pd.DataFrame
    ) -> list[Signal]: ...
