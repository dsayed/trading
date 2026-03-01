"""Tests for the scanner API endpoints."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from trading.api.app import create_app
from trading.api.dependencies import get_database
from trading.core.database import Database
from trading.core.models import (
    AssetClass,
    Direction,
    Instrument,
    Order,
    OrderType,
    Signal,
)


def _make_discover_results(symbols: list[str] | None = None) -> list[dict]:
    """Build realistic engine.discover() return value."""
    symbols = symbols or ["AAPL"]
    results = []
    for i, sym in enumerate(symbols):
        instrument = Instrument(symbol=sym, asset_class=AssetClass.EQUITY)
        results.append({
            "signal": Signal(
                instrument=instrument,
                direction=Direction.LONG,
                conviction=round(0.8 - i * 0.1, 2),
                rationale=f"Bullish signal for {sym}",
                strategy_name="momentum",
                timestamp=datetime.now(),
            ),
            "order": Order(
                instrument=instrument,
                direction=Direction.LONG,
                quantity=20,
                order_type=OrderType.LIMIT,
                limit_price=200.0,
                stop_price=190.0,
                rationale=f"Buy {sym}",
            ),
            "playbook": f"Buy {sym} at $200",
        })
    return results


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "test.db")
    app = create_app()
    app.dependency_overrides[get_database] = lambda: db
    return TestClient(app)


class TestUniversesEndpoint:
    def test_list_universes(self, client):
        resp = client.get("/api/scanner/universes")
        assert resp.status_code == 200
        data = resp.json()
        assert "sp500" in data["predefined"]
        assert "nasdaq100" in data["predefined"]
        assert "forex_majors" in data["predefined"]
        assert "gainers" in data["dynamic"]
        assert "losers" in data["dynamic"]


class TestScannerRunEndpoint:
    @patch("trading.api.routers.scanner.build_engine")
    def test_run_with_custom_symbols(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.discover.return_value = _make_discover_results(["AAPL", "MSFT"])

        resp = client.post("/api/scanner/run", json={
            "symbols": ["AAPL", "MSFT"],
            "strategies": ["momentum"],
            "max_results": 10,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_count"] == 2
        assert data["universe"] == "custom"
        assert len(data["signals"]) == 2
        assert data["signals"][0]["symbol"] == "AAPL"

    @patch("trading.api.routers.scanner.build_engine")
    def test_run_with_universe_requires_discovery(self, mock_build, client):
        mock_engine = mock_build.return_value
        # Provider does NOT implement DiscoveryProvider
        mock_engine.data_provider = MagicMock(spec=[])

        resp = client.post("/api/scanner/run", json={"universe": "sp500"})
        assert resp.status_code == 400
        assert "discovery" in resp.json()["detail"].lower()

    def test_run_without_universe_or_symbols(self, client):
        resp = client.post("/api/scanner/run", json={})
        assert resp.status_code == 422

    @patch("trading.api.routers.scanner.build_engine")
    def test_scanner_saves_results(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.discover.return_value = _make_discover_results()

        resp = client.post("/api/scanner/run", json={"symbols": ["AAPL"]})
        assert resp.status_code == 201
        scan_id = resp.json()["id"]
        assert scan_id > 0

        # Verify saved in scan history
        history = client.get("/api/scans")
        assert any(s["id"] == scan_id for s in history.json())

    @patch("trading.api.routers.scanner.build_engine")
    def test_scanner_response_has_signals(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.discover.return_value = _make_discover_results()

        resp = client.post("/api/scanner/run", json={"symbols": ["AAPL"]})
        signal = resp.json()["signals"][0]
        assert signal["conviction"] == 0.8
        assert signal["direction"] == "long"
        assert signal["playbook"] == "Buy AAPL at $200"
