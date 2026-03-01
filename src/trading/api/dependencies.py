"""FastAPI dependency injection."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends

from trading.core.config import TradingConfig
from trading.core.database import Database
from trading.core.repositories import ConfigRepo, PositionRepo, ScanRepo, WatchlistRepo
from trading.plugins.data.cache import CachingDataProvider

logger = logging.getLogger(__name__)

# Module-level singleton for the shared data provider
_cached_provider: CachingDataProvider | None = None
_provider_key: str = ""


@lru_cache
def get_database() -> Database:
    db_path = Path(os.environ.get("TRADING_DB_PATH", "trading.db"))
    return Database(db_path)


def get_config_repo(db: Database = Depends(get_database)) -> ConfigRepo:
    return ConfigRepo(db)


def get_watchlist_repo(db: Database = Depends(get_database)) -> WatchlistRepo:
    return WatchlistRepo(db)


def get_scan_repo(db: Database = Depends(get_database)) -> ScanRepo:
    return ScanRepo(db)


def get_position_repo(db: Database = Depends(get_database)) -> PositionRepo:
    return PositionRepo(db)


def _build_caching_provider(config: TradingConfig) -> CachingDataProvider:
    """Build a CachingDataProvider from config, reusable across requests."""
    from trading.core.factory import _build_provider
    from trading.plugins.data.base import OptionsDataProvider
    from trading.plugins.data.composite import CompositeDataProvider

    bars_provider = _build_provider(config.data_provider, config)

    if config.options_provider or config.discovery_provider or config.forex_provider:
        options = (
            _build_provider(config.options_provider, config)
            if config.options_provider
            else None
        )
        if options is None and isinstance(bars_provider, OptionsDataProvider):
            options = bars_provider
        discovery = (
            _build_provider(config.discovery_provider, config)
            if config.discovery_provider
            else None
        )
        forex = (
            _build_provider(config.forex_provider, config)
            if config.forex_provider
            else None
        )
        raw_provider: Any = CompositeDataProvider(
            bars_provider,
            options_provider=options,
            discovery_provider=discovery,
            forex_provider=forex,
        )
    else:
        raw_provider = bars_provider

    return CachingDataProvider(raw_provider)


def get_data_provider(
    config_repo: ConfigRepo = Depends(get_config_repo),
) -> CachingDataProvider:
    """Return a shared CachingDataProvider, rebuilt only when provider config changes."""
    global _cached_provider, _provider_key
    config = config_repo.get()
    key = (
        f"{config.data_provider}:{config.options_provider}:"
        f"{config.discovery_provider}:{config.forex_provider}"
    )
    if _cached_provider is None or key != _provider_key:
        logger.info("Building new shared data provider (key: %s)", key)
        _cached_provider = _build_caching_provider(config)
        _provider_key = key
    return _cached_provider


def invalidate_data_provider() -> None:
    """Clear the cached data provider, forcing rebuild on next request."""
    global _cached_provider, _provider_key
    _cached_provider = None
    _provider_key = ""
