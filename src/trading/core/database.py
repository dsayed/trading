"""SQLite database layer for persistence."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DEFAULT_DB_PATH = Path("trading.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stake REAL NOT NULL DEFAULT 10000,
    max_position_pct REAL NOT NULL DEFAULT 0.40,
    stop_loss_pct REAL NOT NULL DEFAULT 0.05,
    data_provider TEXT NOT NULL DEFAULT 'yahoo',
    strategies TEXT NOT NULL DEFAULT '["momentum"]',
    risk_manager TEXT NOT NULL DEFAULT 'fixed_stake',
    broker TEXT NOT NULL DEFAULT 'manual',
    polygon_api_key TEXT,
    options_provider TEXT,
    discovery_provider TEXT,
    fmp_api_key TEXT,
    marketdata_api_key TEXT,
    twelvedata_api_key TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    symbols TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_name TEXT,
    symbols TEXT NOT NULL,
    results TEXT NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,
    ran_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scan_ran_at ON scan(ran_at DESC);

CREATE TABLE IF NOT EXISTS position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL DEFAULT 'equity',
    exchange TEXT,
    tax_lots TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_position_symbol ON position(symbol, asset_class);
"""


class Database:
    """Thin wrapper around sqlite3 with schema management."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a connection that auto-commits on success, rolls back on error."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Run forward-only schema migrations for existing databases."""
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(config)").fetchall()
        }
        if "polygon_api_key" not in columns:
            conn.execute("ALTER TABLE config ADD COLUMN polygon_api_key TEXT")
        for col in (
            "options_provider", "discovery_provider",
            "fmp_api_key", "marketdata_api_key", "twelvedata_api_key",
        ):
            if col not in columns:
                conn.execute(f"ALTER TABLE config ADD COLUMN {col} TEXT")
