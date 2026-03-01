"""Caching wrapper for data providers — reduces API calls with TTL-based caching."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import pandas as pd

from trading.core.models import Instrument, OptionChain
from trading.plugins.data.base import DiscoveryProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

# Default TTLs in seconds
BARS_TTL = 30 * 60       # 30 minutes — bars don't change intraday for swing trading
PRICE_TTL = 5 * 60        # 5 minutes
OPTIONS_TTL = 10 * 60     # 10 minutes
UNIVERSE_TTL = 24 * 60 * 60  # 24 hours — universe membership rarely changes
MOVERS_TTL = 10 * 60      # 10 minutes


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


class CachingDataProvider:
    """Wraps any data provider with a TTL cache. Implements all provider protocols."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._cache: dict[str, _CacheEntry] = {}

    @property
    def name(self) -> str:
        return self._inner.name

    def _get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None or entry.expired:
            return None
        return entry.value

    def _put(self, key: str, value: Any, ttl: float) -> None:
        self._cache[key] = _CacheEntry(value, ttl)

    @property
    def stats(self) -> dict[str, int]:
        """Return cache stats for diagnostics."""
        total = len(self._cache)
        alive = sum(1 for e in self._cache.values() if not e.expired)
        return {"total_entries": total, "active_entries": alive}

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    # --- DataProvider ---

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        key = f"bars:{instrument.symbol}:{start}:{end}"
        cached = self._get(key)
        if cached is not None:
            logger.debug("Cache hit: %s", key)
            return cached
        logger.debug("Cache miss: %s", key)
        result = self._inner.fetch_bars(instrument, start, end)
        self._put(key, result, BARS_TTL)
        return result

    # --- OptionsDataProvider ---

    def fetch_current_price(self, instrument: Instrument) -> float:
        if not isinstance(self._inner, OptionsDataProvider):
            raise NotImplementedError
        key = f"price:{instrument.symbol}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.fetch_current_price(instrument)
        self._put(key, result, PRICE_TTL)
        return result

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        if not isinstance(self._inner, OptionsDataProvider):
            raise NotImplementedError
        key = f"options:{instrument.symbol}:{expiration}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.fetch_option_chain(instrument, expiration)
        self._put(key, result, OPTIONS_TTL)
        return result

    # --- DiscoveryProvider ---

    def list_universe(self, universe_name: str) -> list[str]:
        if not isinstance(self._inner, DiscoveryProvider):
            raise NotImplementedError
        key = f"universe:{universe_name}"
        cached = self._get(key)
        if cached is not None:
            logger.debug("Cache hit: %s", key)
            return cached
        result = self._inner.list_universe(universe_name)
        self._put(key, result, UNIVERSE_TTL)
        return result

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]:
        if not isinstance(self._inner, DiscoveryProvider):
            raise NotImplementedError
        key = f"movers:{direction}:{limit}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.get_movers(direction, limit)
        self._put(key, result, MOVERS_TTL)
        return result

    # --- Protocol compliance helpers ---

    def __getattr__(self, name: str) -> Any:
        """Forward any other attribute access to the inner provider."""
        return getattr(self._inner, name)
