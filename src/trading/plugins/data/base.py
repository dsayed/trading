"""DataProvider protocol — all data source plugins implement this."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument, OptionChain


@runtime_checkable
class DataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame: ...


@runtime_checkable
class OptionsDataProvider(Protocol):
    """Protocol for providers that can fetch option chain data."""

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]: ...

    def fetch_current_price(self, instrument: Instrument) -> float: ...
