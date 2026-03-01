"""FastAPI dependency injection."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from trading.core.database import Database
from trading.core.repositories import ConfigRepo, PositionRepo, ScanRepo, WatchlistRepo


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
