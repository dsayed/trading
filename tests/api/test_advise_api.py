"""Tests for the advise API endpoint."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from trading.api.app import create_app
from trading.api.dependencies import get_database
from trading.core.database import Database
from trading.core.models import (
    AssetClass,
    Instrument,
    Play,
    PlayType,
    Position,
    TaxLot,
)


def _make_advise_results(positions):
    """Build a realistic engine.advise() return value."""
    results = []
    for pos in positions:
        results.append({
            "position": pos,
            "current_price": 200.0,
            "unrealized_pnl": pos.unrealized_pnl(200.0),
            "plays": [
                Play(
                    position=pos,
                    play_type=PlayType.HOLD,
                    title=f"Hold {pos.instrument.symbol}",
                    rationale="No strong signal to act",
                    conviction=0.50,
                    playbook="1. Continue holding",
                    advisor_name="stock_play",
                ),
                Play(
                    position=pos,
                    play_type=PlayType.STOP_LOSS,
                    title=f"Set stop-loss on {pos.instrument.symbol}",
                    rationale="Protect against downside",
                    conviction=0.70,
                    max_loss=1000.0,
                    playbook="1. Place STOP order at $190\n2. Quantity: 100 shares",
                    advisor_name="stock_play",
                ),
            ],
        })
    return results


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "test.db")
    app = create_app()
    app.dependency_overrides[get_database] = lambda: db
    return TestClient(app)


def _seed_position(client):
    """Create a position and return its ID."""
    resp = client.post("/api/positions", json={
        "symbol": "AAPL",
        "quantity": 100,
        "cost_basis": 180.0,
        "purchase_date": "2025-06-01",
    })
    return resp.json()["id"]


class TestAdviseAPI:
    @patch("trading.api.routers.advise.build_engine")
    @patch("trading.api.routers.advise.build_advisors")
    def test_advise_all_positions(self, mock_advisors, mock_engine, client):
        pid = _seed_position(client)

        def fake_advise(positions, advisors, lookback_days):
            return _make_advise_results(positions)

        mock_engine.return_value.advise = fake_advise
        mock_advisors.return_value = ["fake_advisor"]

        resp = client.post("/api/advise", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][0]["current_price"] == 200.0
        assert len(data["positions"][0]["plays"]) == 2

    @patch("trading.api.routers.advise.build_engine")
    @patch("trading.api.routers.advise.build_advisors")
    def test_advise_specific_positions(self, mock_advisors, mock_engine, client):
        pid = _seed_position(client)

        def fake_advise(positions, advisors, lookback_days):
            return _make_advise_results(positions)

        mock_engine.return_value.advise = fake_advise
        mock_advisors.return_value = ["fake_advisor"]

        resp = client.post("/api/advise", json={"position_ids": [pid]})
        assert resp.status_code == 200
        assert len(resp.json()["positions"]) == 1

    def test_advise_no_positions(self, client):
        resp = client.post("/api/advise", json={})
        assert resp.status_code == 422
        assert "No positions" in resp.json()["detail"]

    def test_advise_nonexistent_position(self, client):
        resp = client.post("/api/advise", json={"position_ids": [999]})
        assert resp.status_code == 404

    @patch("trading.api.routers.advise.build_engine")
    @patch("trading.api.routers.advise.build_advisors")
    def test_advise_play_has_fields(self, mock_advisors, mock_engine, client):
        _seed_position(client)

        def fake_advise(positions, advisors, lookback_days):
            return _make_advise_results(positions)

        mock_engine.return_value.advise = fake_advise
        mock_advisors.return_value = ["fake_advisor"]

        resp = client.post("/api/advise", json={})
        play = resp.json()["positions"][0]["plays"][0]
        assert play["play_type"] == "hold"
        assert play["title"] == "Hold AAPL"
        assert play["conviction"] == 0.50
        assert play["advisor_name"] == "stock_play"
        assert "1." in play["playbook"]

    @patch("trading.api.routers.advise.build_engine")
    @patch("trading.api.routers.advise.build_advisors")
    def test_advise_invalid_advisors(self, mock_advisors, mock_engine, client):
        _seed_position(client)
        mock_advisors.return_value = []

        resp = client.post("/api/advise", json={"advisor_names": ["nonexistent"]})
        assert resp.status_code == 422
        assert "No valid advisors" in resp.json()["detail"]
