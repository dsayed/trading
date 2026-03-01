"""Tests for data access repositories."""

import pytest

from trading.core.database import Database
from trading.core.models import AssetClass
from trading.core.repositories import ConfigRepo, PositionRepo, ScanRepo, WatchlistRepo


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


# --------------------------------------------------------------------------- #
#  ConfigRepo
# --------------------------------------------------------------------------- #


class TestConfigRepo:
    def test_get_returns_defaults_when_empty(self, db):
        repo = ConfigRepo(db)
        config = repo.get()
        assert config.stake == 10_000
        assert config.strategies == ["momentum"]

    def test_update_creates_row(self, db):
        repo = ConfigRepo(db)
        config = repo.update(stake=5000)
        assert config.stake == 5000

    def test_update_partial(self, db):
        repo = ConfigRepo(db)
        repo.update(stake=5000)
        config = repo.update(stop_loss_pct=0.03)
        assert config.stake == 5000  # unchanged
        assert config.stop_loss_pct == 0.03  # updated

    def test_update_persists(self, db):
        repo = ConfigRepo(db)
        repo.update(stake=7500, max_position_pct=0.30)
        config = repo.get()
        assert config.stake == 7500
        assert config.max_position_pct == 0.30

    def test_seed_from_toml(self, db, tmp_path):
        toml_path = tmp_path / "config.toml"
        toml_path.write_text(
            '[trading]\nstake = 25000\nwatchlist = ["TSLA"]\n'
        )
        repo = ConfigRepo(db)
        repo.seed_from_toml(toml_path)
        config = repo.get()
        assert config.stake == 25000

    def test_seed_skips_if_exists(self, db, tmp_path):
        repo = ConfigRepo(db)
        repo.update(stake=5000)

        toml_path = tmp_path / "config.toml"
        toml_path.write_text("[trading]\nstake = 99999\n")
        repo.seed_from_toml(toml_path)
        assert repo.get().stake == 5000  # not overwritten


# --------------------------------------------------------------------------- #
#  WatchlistRepo
# --------------------------------------------------------------------------- #


class TestWatchlistRepo:
    def test_create_and_get(self, db):
        repo = WatchlistRepo(db)
        wl = repo.create("Tech", ["AAPL", "MSFT"])
        assert wl.name == "Tech"
        assert wl.symbols == ["AAPL", "MSFT"]

        fetched = repo.get(wl.id)
        assert fetched is not None
        assert fetched.name == "Tech"

    def test_list_all(self, db):
        repo = WatchlistRepo(db)
        repo.create("Alpha", ["AAPL"])
        repo.create("Beta", ["MSFT"])
        all_wl = repo.list_all()
        assert len(all_wl) == 2
        assert all_wl[0].name == "Alpha"  # ordered by name

    def test_get_by_name(self, db):
        repo = WatchlistRepo(db)
        repo.create("MyList", ["GOOG"])
        wl = repo.get_by_name("MyList")
        assert wl is not None
        assert wl.symbols == ["GOOG"]

    def test_update_name(self, db):
        repo = WatchlistRepo(db)
        wl = repo.create("Old", ["AAPL"])
        updated = repo.update(wl.id, name="New")
        assert updated.name == "New"
        assert updated.symbols == ["AAPL"]

    def test_update_symbols(self, db):
        repo = WatchlistRepo(db)
        wl = repo.create("List", ["AAPL"])
        updated = repo.update(wl.id, symbols=["AAPL", "MSFT", "GOOG"])
        assert updated.symbols == ["AAPL", "MSFT", "GOOG"]

    def test_delete(self, db):
        repo = WatchlistRepo(db)
        wl = repo.create("ToDelete", ["AAPL"])
        assert repo.delete(wl.id) is True
        assert repo.get(wl.id) is None

    def test_delete_nonexistent(self, db):
        repo = WatchlistRepo(db)
        assert repo.delete(999) is False

    def test_get_nonexistent(self, db):
        repo = WatchlistRepo(db)
        assert repo.get(999) is None

    def test_update_nonexistent(self, db):
        repo = WatchlistRepo(db)
        assert repo.update(999, name="Nope") is None

    def test_duplicate_name_raises(self, db):
        repo = WatchlistRepo(db)
        repo.create("Unique")
        with pytest.raises(Exception):
            repo.create("Unique")

    def test_seed_from_toml(self, db, tmp_path):
        toml_path = tmp_path / "config.toml"
        toml_path.write_text(
            '[trading]\nwatchlist = ["AAPL", "MSFT"]\n'
        )
        repo = WatchlistRepo(db)
        repo.seed_from_toml(toml_path)
        all_wl = repo.list_all()
        assert len(all_wl) == 1
        assert all_wl[0].name == "Default"
        assert all_wl[0].symbols == ["AAPL", "MSFT"]

    def test_seed_skips_if_watchlists_exist(self, db, tmp_path):
        repo = WatchlistRepo(db)
        repo.create("Existing", ["GOOG"])
        toml_path = tmp_path / "config.toml"
        toml_path.write_text('[trading]\nwatchlist = ["AAPL"]\n')
        repo.seed_from_toml(toml_path)
        assert len(repo.list_all()) == 1  # no "Default" created


# --------------------------------------------------------------------------- #
#  ScanRepo
# --------------------------------------------------------------------------- #


class TestScanRepo:
    def test_save_and_get(self, db):
        repo = ScanRepo(db)
        record = repo.save(
            symbols=["AAPL", "MSFT"],
            results=[{"signal": "test"}],
            watchlist_name="Tech",
        )
        assert record.signal_count == 1
        assert record.watchlist_name == "Tech"

        fetched = repo.get(record.id)
        assert fetched is not None
        assert fetched.results == [{"signal": "test"}]

    def test_list_recent(self, db):
        repo = ScanRepo(db)
        repo.save(symbols=["AAPL"], results=[])
        repo.save(symbols=["MSFT"], results=[{"s": 1}])
        summaries = repo.list_recent(limit=10)
        assert len(summaries) == 2
        # Most recent first
        assert summaries[0].symbols == ["MSFT"]

    def test_list_recent_respects_limit(self, db):
        repo = ScanRepo(db)
        for i in range(5):
            repo.save(symbols=[f"SYM{i}"], results=[])
        assert len(repo.list_recent(limit=3)) == 3

    def test_get_nonexistent(self, db):
        repo = ScanRepo(db)
        assert repo.get(999) is None

    def test_save_without_watchlist(self, db):
        repo = ScanRepo(db)
        record = repo.save(symbols=["AAPL"], results=[])
        assert record.watchlist_name is None


# --------------------------------------------------------------------------- #
#  PositionRepo
# --------------------------------------------------------------------------- #


class TestPositionRepo:
    def test_create_and_get(self, db):
        repo = PositionRepo(db)
        rec = repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        assert rec.symbol == "AAPL"
        assert rec.asset_class == "equity"
        assert len(rec.tax_lots) == 1
        assert rec.tax_lots[0]["quantity"] == 100

        fetched = repo.get(rec.id)
        assert fetched is not None
        assert fetched.symbol == "AAPL"

    def test_list_all(self, db):
        repo = PositionRepo(db)
        repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        repo.create("MSFT", quantity=50, cost_basis=300.0, purchase_date="2025-06-01")
        all_pos = repo.list_all()
        assert len(all_pos) == 2
        assert all_pos[0].symbol == "AAPL"  # ordered by symbol

    def test_get_by_symbol(self, db):
        repo = PositionRepo(db)
        repo.create("GOOG", quantity=30, cost_basis=150.0, purchase_date="2025-06-01")
        rec = repo.get_by_symbol("GOOG")
        assert rec is not None
        assert rec.symbol == "GOOG"

    def test_add_tax_lot(self, db):
        repo = PositionRepo(db)
        rec = repo.create("AAPL", quantity=50, cost_basis=180.0, purchase_date="2025-06-01")
        updated = repo.add_tax_lot(rec.id, quantity=30, cost_basis=195.0, purchase_date="2026-01-15")
        assert updated is not None
        assert len(updated.tax_lots) == 2
        assert updated.tax_lots[1]["quantity"] == 30
        assert updated.tax_lots[1]["cost_basis"] == 195.0

    def test_add_tax_lot_nonexistent(self, db):
        repo = PositionRepo(db)
        result = repo.add_tax_lot(999, quantity=50, cost_basis=100.0, purchase_date="2025-06-01")
        assert result is None

    def test_update_notes(self, db):
        repo = PositionRepo(db)
        rec = repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        updated = repo.update(rec.id, notes="Long-term hold")
        assert updated is not None
        assert updated.notes == "Long-term hold"

    def test_update_nonexistent(self, db):
        repo = PositionRepo(db)
        assert repo.update(999, notes="test") is None

    def test_delete(self, db):
        repo = PositionRepo(db)
        rec = repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        assert repo.delete(rec.id) is True
        assert repo.get(rec.id) is None

    def test_delete_nonexistent(self, db):
        repo = PositionRepo(db)
        assert repo.delete(999) is False

    def test_get_nonexistent(self, db):
        repo = PositionRepo(db)
        assert repo.get(999) is None

    def test_duplicate_symbol_raises(self, db):
        repo = PositionRepo(db)
        repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        with pytest.raises(Exception):
            repo.create("AAPL", quantity=50, cost_basis=190.0, purchase_date="2026-01-01")

    def test_to_domain(self, db):
        repo = PositionRepo(db)
        rec = repo.create("AAPL", quantity=100, cost_basis=180.0, purchase_date="2025-06-01")
        rec = repo.add_tax_lot(rec.id, quantity=50, cost_basis=195.0, purchase_date="2026-01-15")
        pos = repo.to_domain(rec)
        assert pos.instrument.symbol == "AAPL"
        assert pos.instrument.asset_class == AssetClass.EQUITY
        assert pos.total_quantity == 150
        assert len(pos.tax_lots) == 2
