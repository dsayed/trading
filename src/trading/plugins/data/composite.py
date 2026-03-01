"""Composite data provider — routes calls to role-specific sub-providers.

Allows mixing providers per data type, e.g. FMP for discovery,
MarketData for options, Yahoo for bars.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from trading.core.models import Instrument, OptionChain


class CompositeDataProvider:
    """Routes data calls to role-specific sub-providers.

    Structurally satisfies DataProvider, OptionsDataProvider, and
    DiscoveryProvider protocols. Methods raise NotImplementedError
    with clear messages when a role has no configured provider.
    """

    def __init__(
        self,
        bars_provider: Any,
        options_provider: Any | None = None,
        discovery_provider: Any | None = None,
    ) -> None:
        self._bars_provider = bars_provider
        self._options_provider = options_provider
        self._discovery_provider = discovery_provider

    @property
    def name(self) -> str:
        parts = [self._bars_provider.name]
        if self._options_provider and self._options_provider is not self._bars_provider:
            parts.append(self._options_provider.name)
        if self._discovery_provider and self._discovery_provider is not self._bars_provider:
            parts.append(self._discovery_provider.name)
        return "+".join(dict.fromkeys(parts))  # deduplicated, ordered

    @property
    def supports_options(self) -> bool:
        return self._options_provider is not None

    @property
    def supports_discovery(self) -> bool:
        return self._discovery_provider is not None

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        return self._bars_provider.fetch_bars(instrument, start, end)

    # ── OptionsDataProvider ───────────────────────────────────────────

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        if self._options_provider is None:
            raise NotImplementedError(
                "No options provider configured. Set options_provider in settings "
                "to a provider that supports options (yahoo, polygon, marketdata, twelvedata)."
            )
        return self._options_provider.fetch_option_chain(instrument, expiration)

    def fetch_current_price(self, instrument: Instrument) -> float:
        if self._options_provider is None:
            raise NotImplementedError(
                "No options provider configured. Set options_provider in settings."
            )
        return self._options_provider.fetch_current_price(instrument)

    # ── DiscoveryProvider ─────────────────────────────────────────────

    def list_universe(self, universe_name: str) -> list[str]:
        if self._discovery_provider is None:
            raise NotImplementedError(
                "No discovery provider configured. Set discovery_provider in settings "
                "to a provider that supports discovery (polygon, fmp)."
            )
        return self._discovery_provider.list_universe(universe_name)

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]:
        if self._discovery_provider is None:
            raise NotImplementedError(
                "No discovery provider configured. Set discovery_provider in settings "
                "to a provider that supports discovery (polygon, fmp)."
            )
        return self._discovery_provider.get_movers(direction, limit)
