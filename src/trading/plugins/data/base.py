"""DataProvider protocol — all data source plugins implement this."""

from __future__ import annotations

import logging
from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

from trading.core.models import Instrument, OptionChain

_api_logger = logging.getLogger("trading.api_calls")


def log_api_call(
    provider: str,
    method: str,
    url: str,
    elapsed_ms: float,
    status: str = "ok",
    error: str | None = None,
) -> None:
    """Log an API call with timing for diagnostics."""
    msg = f"{provider} {method} {url} {elapsed_ms:.0f}ms {status}"
    if error:
        msg += f" ({error})"
    _api_logger.info(msg)


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


@runtime_checkable
class DiscoveryProvider(Protocol):
    """Protocol for providers that can discover tradeable universes and movers."""

    def list_universe(self, universe_name: str) -> list[str]: ...

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]: ...
