"""DataProvider protocol — all data source plugins implement this."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument


@runtime_checkable
class DataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame: ...
