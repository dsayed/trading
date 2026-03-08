"""PostgreSQL connection to Supabase for cloud market data storage.

Usage:
    db = CloudDatabase()            # reads SUPABASE_DB_URL from env
    db = CloudDatabase(url="...")   # explicit URL

    rows = db.execute("SELECT * FROM equity_bars WHERE symbol = %s", ("AAPL",))
    db.executemany("INSERT INTO macro_series ...", rows)
    with db.connection() as conn:   # raw psycopg2 connection
        ...
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)


class CloudDatabase:
    """Manages PostgreSQL connection to Supabase for market data."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.environ.get("SUPABASE_DB_URL")

    @property
    def is_configured(self) -> bool:
        return bool(self._url)

    def _connection_url(self) -> str:
        """Ensure sslmode=require is set for Supabase connections."""
        url = self._url or ""
        if "supabase" in url and "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}sslmode=require"
        return url

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        if not self._url:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. "
                "Add it to your environment or .env file."
            )
        import psycopg2

        conn = psycopg2.connect(self._connection_url())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Run a SQL statement and return rows as dicts."""
        import psycopg2.extras

        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                return []

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """Run a SQL statement for each row in params_list."""
        if not params_list:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, params_list)

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], conflict_cols: list[str]) -> int:
        """Generic upsert: INSERT ... ON CONFLICT (cols) DO UPDATE SET ..."""
        if not rows:
            return 0

        cols = list(rows[0].keys())
        col_str = ", ".join(cols)
        placeholder_str = ", ".join(["%s"] * len(cols))
        conflict_str = ", ".join(conflict_cols)
        update_str = ", ".join(
            f"{c} = EXCLUDED.{c}"
            for c in cols
            if c not in conflict_cols
        )

        sql = (
            f"INSERT INTO {table} ({col_str}) VALUES ({placeholder_str}) "
            f"ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}"
        )
        params_list = [tuple(row[c] for c in cols) for row in rows]
        self.executemany(sql, params_list)
        return len(rows)
