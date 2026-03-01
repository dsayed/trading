"""Tests for the SQLite database layer."""

from trading.core.database import Database


class TestDatabase:
    def test_creates_schema(self, tmp_path):
        db = Database(tmp_path / "test.db")
        with db.connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        names = [t["name"] for t in tables]
        assert "config" in names
        assert "watchlist" in names
        assert "scan" in names

    def test_idempotent_schema(self, tmp_path):
        db_path = tmp_path / "test.db"
        Database(db_path)
        Database(db_path)  # second init should not raise

    def test_wal_mode(self, tmp_path):
        db = Database(tmp_path / "test.db")
        with db.connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode[0] == "wal"

    def test_position_table_exists(self, tmp_path):
        db = Database(tmp_path / "test.db")
        with db.connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        names = [t["name"] for t in tables]
        assert "position" in names

    def test_rollback_on_error(self, tmp_path):
        db = Database(tmp_path / "test.db")
        try:
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO watchlist (name, symbols) VALUES (?, ?)",
                    ("test", "[]"),
                )
                raise ValueError("force rollback")
        except ValueError:
            pass

        with db.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()
        assert count[0] == 0
