"""Tests for the scan API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pandas as pd
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


def _make_scan_results() -> list[dict]:
    """Build a realistic engine.scan() return value."""
    instrument = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
    return [
        {
            "signal": Signal(
                instrument=instrument,
                direction=Direction.LONG,
                conviction=0.72,
                rationale="SMA crossover bullish",
                strategy_name="momentum",
                timestamp=datetime.now(),
            ),
            "order": Order(
                instrument=instrument,
                direction=Direction.LONG,
                quantity=18,
                order_type=OrderType.LIMIT,
                limit_price=223.50,
                stop_price=212.33,
                rationale="Buy 18 shares at $223.50",
            ),
            "playbook": "1. Open broker\n2. Buy 18 AAPL\n3. Limit $223.50",
        }
    ]


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "test.db")
    app = create_app()
    app.dependency_overrides[get_database] = lambda: db
    return TestClient(app)


class TestScansAPI:
    @patch("trading.api.routers.scans.build_engine")
    def test_run_scan_with_symbols(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = _make_scan_results()

        resp = client.post("/api/scans", json={"symbols": ["AAPL"]})
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_count"] == 1
        assert len(data["signals"]) == 1
        assert data["signals"][0]["symbol"] == "AAPL"
        assert data["signals"][0]["direction"] == "long"
        assert data["signals"][0]["conviction"] == 0.72

    @patch("trading.api.routers.scans.build_engine")
    def test_run_scan_with_watchlist(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = _make_scan_results()

        # Create a watchlist first
        wl_resp = client.post(
            "/api/watchlists", json={"name": "Test", "symbols": ["AAPL"]}
        )
        wl_id = wl_resp.json()["id"]

        resp = client.post("/api/scans", json={"watchlist_id": wl_id})
        assert resp.status_code == 201
        assert resp.json()["signal_count"] == 1

    def test_run_scan_without_symbols_or_watchlist(self, client):
        resp = client.post("/api/scans", json={})
        assert resp.status_code == 422

    def test_run_scan_nonexistent_watchlist(self, client):
        resp = client.post("/api/scans", json={"watchlist_id": 999})
        assert resp.status_code == 404

    @patch("trading.api.routers.scans.build_engine")
    def test_list_scans(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = _make_scan_results()
        client.post("/api/scans", json={"symbols": ["AAPL"]})

        resp = client.get("/api/scans")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["signal_count"] == 1

    @patch("trading.api.routers.scans.build_engine")
    def test_get_scan_by_id(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = _make_scan_results()
        create_resp = client.post("/api/scans", json={"symbols": ["AAPL"]})
        scan_id = create_resp.json()["id"]

        resp = client.get(f"/api/scans/{scan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == scan_id
        assert len(data["signals"]) == 1

    def test_get_nonexistent_scan(self, client):
        resp = client.get("/api/scans/999")
        assert resp.status_code == 404

    @patch("trading.api.routers.scans.build_engine")
    def test_scan_response_has_playbook(self, mock_build, client):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = _make_scan_results()

        resp = client.post("/api/scans", json={"symbols": ["AAPL"]})
        signal = resp.json()["signals"][0]
        assert "Open broker" in signal["playbook"]
        assert signal["limit_price"] == 223.50
        assert signal["stop_price"] == 212.33
