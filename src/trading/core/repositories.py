"""Data access layer — repositories for config, watchlists, scans, and positions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from trading.core.config import TradingConfig, load_config
from trading.core.database import Database
from trading.core.models import AssetClass, Instrument, Position, TaxLot


# --------------------------------------------------------------------------- #
#  Data transfer objects for watchlist and scan rows
# --------------------------------------------------------------------------- #


@dataclass
class Watchlist:
    id: int
    name: str
    symbols: list[str]
    created_at: str
    updated_at: str


@dataclass
class ScanRecord:
    id: int
    watchlist_name: str | None
    symbols: list[str]
    results: list[dict]
    signal_count: int
    ran_at: str


@dataclass
class ScanSummary:
    id: int
    watchlist_name: str | None
    symbols: list[str]
    signal_count: int
    ran_at: str


# --------------------------------------------------------------------------- #
#  Config repository
# --------------------------------------------------------------------------- #


class ConfigRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self) -> TradingConfig:
        """Get current config from DB, or defaults if table is empty."""
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM config WHERE id = 1").fetchone()
        if row is None:
            return TradingConfig()
        return TradingConfig(
            stake=row["stake"],
            max_position_pct=row["max_position_pct"],
            stop_loss_pct=row["stop_loss_pct"],
            data_provider=row["data_provider"],
            strategies=json.loads(row["strategies"]),
            risk_manager=row["risk_manager"],
            broker=row["broker"],
            polygon_api_key=row["polygon_api_key"],
            options_provider=row["options_provider"],
            discovery_provider=row["discovery_provider"],
            fmp_api_key=row["fmp_api_key"],
            marketdata_api_key=row["marketdata_api_key"],
            twelvedata_api_key=row["twelvedata_api_key"],
        )

    def update(self, **kwargs: object) -> TradingConfig:
        """Update config fields. Only provided fields are changed."""
        current = self.get()
        updates = {k: v for k, v in kwargs.items() if v is not None}
        new = current.model_copy(update=updates)

        with self._db.connection() as conn:
            conn.execute(
                """INSERT INTO config (id, stake, max_position_pct, stop_loss_pct,
                   data_provider, strategies, risk_manager, broker,
                   polygon_api_key, options_provider, discovery_provider,
                   fmp_api_key, marketdata_api_key, twelvedata_api_key,
                   updated_at)
                   VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(id) DO UPDATE SET
                     stake=excluded.stake,
                     max_position_pct=excluded.max_position_pct,
                     stop_loss_pct=excluded.stop_loss_pct,
                     data_provider=excluded.data_provider,
                     strategies=excluded.strategies,
                     risk_manager=excluded.risk_manager,
                     broker=excluded.broker,
                     polygon_api_key=excluded.polygon_api_key,
                     options_provider=excluded.options_provider,
                     discovery_provider=excluded.discovery_provider,
                     fmp_api_key=excluded.fmp_api_key,
                     marketdata_api_key=excluded.marketdata_api_key,
                     twelvedata_api_key=excluded.twelvedata_api_key,
                     updated_at=excluded.updated_at""",
                (
                    new.stake,
                    new.max_position_pct,
                    new.stop_loss_pct,
                    new.data_provider,
                    json.dumps(new.strategies),
                    new.risk_manager,
                    new.broker,
                    new.polygon_api_key,
                    new.options_provider,
                    new.discovery_provider,
                    new.fmp_api_key,
                    new.marketdata_api_key,
                    new.twelvedata_api_key,
                ),
            )
        return new

    def seed_from_toml(self, toml_path: Path = Path("config.toml")) -> None:
        """Seed config from TOML file if the config table is empty."""
        with self._db.connection() as conn:
            row = conn.execute("SELECT id FROM config WHERE id = 1").fetchone()
        if row is not None:
            return  # already seeded

        config = load_config(toml_path)
        self.update(
            stake=config.stake,
            max_position_pct=config.max_position_pct,
            stop_loss_pct=config.stop_loss_pct,
            data_provider=config.data_provider,
            strategies=config.strategies,
            risk_manager=config.risk_manager,
            broker=config.broker,
        )


# --------------------------------------------------------------------------- #
#  Watchlist repository
# --------------------------------------------------------------------------- #


class WatchlistRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_all(self) -> list[Watchlist]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY name"
            ).fetchall()
        return [self._to_watchlist(r) for r in rows]

    def get(self, watchlist_id: int) -> Watchlist | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (watchlist_id,)
            ).fetchone()
        return self._to_watchlist(row) if row else None

    def get_by_name(self, name: str) -> Watchlist | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE name = ?", (name,)
            ).fetchone()
        return self._to_watchlist(row) if row else None

    def create(self, name: str, symbols: list[str] | None = None) -> Watchlist:
        symbols = symbols or []
        with self._db.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO watchlist (name, symbols) VALUES (?, ?)",
                (name, json.dumps(symbols)),
            )
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._to_watchlist(row)

    def update(
        self,
        watchlist_id: int,
        name: str | None = None,
        symbols: list[str] | None = None,
    ) -> Watchlist | None:
        current = self.get(watchlist_id)
        if current is None:
            return None

        new_name = name if name is not None else current.name
        new_symbols = symbols if symbols is not None else current.symbols

        with self._db.connection() as conn:
            conn.execute(
                """UPDATE watchlist
                   SET name = ?, symbols = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (new_name, json.dumps(new_symbols), watchlist_id),
            )
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (watchlist_id,)
            ).fetchone()
        return self._to_watchlist(row)

    def delete(self, watchlist_id: int) -> bool:
        with self._db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM watchlist WHERE id = ?", (watchlist_id,)
            )
        return cursor.rowcount > 0

    def seed_from_toml(self, toml_path: Path = Path("config.toml")) -> None:
        """Create a 'Default' watchlist from config.toml if no watchlists exist."""
        if self.list_all():
            return  # already have watchlists
        config = load_config(toml_path)
        if config.watchlist:
            self.create("Default", config.watchlist)

    @staticmethod
    def _to_watchlist(row: object) -> Watchlist:
        return Watchlist(
            id=row["id"],  # type: ignore[index]
            name=row["name"],  # type: ignore[index]
            symbols=json.loads(row["symbols"]),  # type: ignore[index]
            created_at=row["created_at"],  # type: ignore[index]
            updated_at=row["updated_at"],  # type: ignore[index]
        )


# --------------------------------------------------------------------------- #
#  Scan repository
# --------------------------------------------------------------------------- #


class ScanRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(
        self,
        symbols: list[str],
        results: list[dict],
        watchlist_name: str | None = None,
    ) -> ScanRecord:
        with self._db.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO scan (watchlist_name, symbols, results, signal_count)
                   VALUES (?, ?, ?, ?)""",
                (
                    watchlist_name,
                    json.dumps(symbols),
                    json.dumps(results),
                    len(results),
                ),
            )
            row = conn.execute(
                "SELECT * FROM scan WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._to_record(row)

    def list_recent(self, limit: int = 20) -> list[ScanSummary]:
        with self._db.connection() as conn:
            rows = conn.execute(
                """SELECT id, watchlist_name, symbols, signal_count, ran_at
                   FROM scan ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            ScanSummary(
                id=r["id"],
                watchlist_name=r["watchlist_name"],
                symbols=json.loads(r["symbols"]),
                signal_count=r["signal_count"],
                ran_at=r["ran_at"],
            )
            for r in rows
        ]

    def get(self, scan_id: int) -> ScanRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM scan WHERE id = ?", (scan_id,)
            ).fetchone()
        return self._to_record(row) if row else None

    @staticmethod
    def _to_record(row: object) -> ScanRecord:
        return ScanRecord(
            id=row["id"],  # type: ignore[index]
            watchlist_name=row["watchlist_name"],  # type: ignore[index]
            symbols=json.loads(row["symbols"]),  # type: ignore[index]
            results=json.loads(row["results"]),  # type: ignore[index]
            signal_count=row["signal_count"],  # type: ignore[index]
            ran_at=row["ran_at"],  # type: ignore[index]
        )


# --------------------------------------------------------------------------- #
#  Position data transfer object and repository
# --------------------------------------------------------------------------- #


@dataclass
class PositionRecord:
    id: int
    symbol: str
    asset_class: str
    exchange: str | None
    tax_lots: list[dict]
    notes: str | None
    created_at: str
    updated_at: str


class PositionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_all(self) -> list[PositionRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM position ORDER BY symbol"
            ).fetchall()
        return [self._to_record(r) for r in rows]

    def get(self, position_id: int) -> PositionRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM position WHERE id = ?", (position_id,)
            ).fetchone()
        return self._to_record(row) if row else None

    def get_by_symbol(self, symbol: str, asset_class: str = "equity") -> PositionRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM position WHERE symbol = ? AND asset_class = ?",
                (symbol, asset_class),
            ).fetchone()
        return self._to_record(row) if row else None

    def create(
        self,
        symbol: str,
        quantity: int,
        cost_basis: float,
        purchase_date: str,
        asset_class: str = "equity",
        exchange: str | None = None,
        notes: str | None = None,
    ) -> PositionRecord:
        tax_lots = [
            {
                "quantity": quantity,
                "cost_basis": cost_basis,
                "purchase_date": purchase_date,
            }
        ]
        with self._db.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO position (symbol, asset_class, exchange, tax_lots, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (symbol, asset_class, exchange, json.dumps(tax_lots), notes),
            )
            row = conn.execute(
                "SELECT * FROM position WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._to_record(row)

    def add_tax_lot(
        self,
        position_id: int,
        quantity: int,
        cost_basis: float,
        purchase_date: str,
    ) -> PositionRecord | None:
        current = self.get(position_id)
        if current is None:
            return None

        lots = current.tax_lots
        lots.append({
            "quantity": quantity,
            "cost_basis": cost_basis,
            "purchase_date": purchase_date,
        })

        with self._db.connection() as conn:
            conn.execute(
                """UPDATE position SET tax_lots = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(lots), position_id),
            )
            row = conn.execute(
                "SELECT * FROM position WHERE id = ?", (position_id,)
            ).fetchone()
        return self._to_record(row)

    def update(
        self,
        position_id: int,
        notes: str | None = None,
    ) -> PositionRecord | None:
        current = self.get(position_id)
        if current is None:
            return None

        new_notes = notes if notes is not None else current.notes

        with self._db.connection() as conn:
            conn.execute(
                """UPDATE position SET notes = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (new_notes, position_id),
            )
            row = conn.execute(
                "SELECT * FROM position WHERE id = ?", (position_id,)
            ).fetchone()
        return self._to_record(row)

    def delete(self, position_id: int) -> bool:
        with self._db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM position WHERE id = ?", (position_id,)
            )
        return cursor.rowcount > 0

    def to_domain(self, record: PositionRecord) -> Position:
        """Convert a DB record to a domain Position model."""
        instrument = Instrument(
            symbol=record.symbol,
            asset_class=AssetClass(record.asset_class),
            exchange=record.exchange,
        )
        tax_lots = [
            TaxLot(
                instrument=instrument,
                quantity=lot["quantity"],
                cost_basis=lot["cost_basis"],
                purchase_date=date.fromisoformat(lot["purchase_date"]),
            )
            for lot in record.tax_lots
        ]
        return Position(instrument=instrument, tax_lots=tax_lots)

    @staticmethod
    def _to_record(row: object) -> PositionRecord:
        return PositionRecord(
            id=row["id"],  # type: ignore[index]
            symbol=row["symbol"],  # type: ignore[index]
            asset_class=row["asset_class"],  # type: ignore[index]
            exchange=row["exchange"],  # type: ignore[index]
            tax_lots=json.loads(row["tax_lots"]),  # type: ignore[index]
            notes=row["notes"],  # type: ignore[index]
            created_at=row["created_at"],  # type: ignore[index]
            updated_at=row["updated_at"],  # type: ignore[index]
        )
