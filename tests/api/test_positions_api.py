"""Tests for the positions API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from trading.api.app import create_app
from trading.api.dependencies import get_database
from trading.core.database import Database


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "test.db")
    app = create_app()
    app.dependency_overrides[get_database] = lambda: db
    return TestClient(app)


class TestPositionsAPI:
    def test_list_positions_empty(self, client):
        resp = client.get("/api/positions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_position(self, client):
        resp = client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 100,
            "cost_basis": 180.0,
            "purchase_date": "2025-06-01",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["total_quantity"] == 100
        assert data["average_cost"] == 180.0
        assert len(data["tax_lots"]) == 1

    def test_create_position_uppercases_symbol(self, client):
        resp = client.post("/api/positions", json={
            "symbol": "aapl",
            "quantity": 50,
            "cost_basis": 180.0,
            "purchase_date": "2025-06-01",
        })
        assert resp.json()["symbol"] == "AAPL"

    def test_get_position(self, client):
        create_resp = client.post("/api/positions", json={
            "symbol": "MSFT",
            "quantity": 50,
            "cost_basis": 300.0,
            "purchase_date": "2025-06-01",
        })
        pid = create_resp.json()["id"]

        resp = client.get(f"/api/positions/{pid}")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "MSFT"

    def test_get_nonexistent_position(self, client):
        resp = client.get("/api/positions/999")
        assert resp.status_code == 404

    def test_add_tax_lot(self, client):
        create_resp = client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 50,
            "cost_basis": 180.0,
            "purchase_date": "2025-06-01",
        })
        pid = create_resp.json()["id"]

        resp = client.post(f"/api/positions/{pid}/lots", json={
            "quantity": 30,
            "cost_basis": 195.0,
            "purchase_date": "2026-01-15",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_quantity"] == 80
        assert len(data["tax_lots"]) == 2

    def test_add_tax_lot_nonexistent(self, client):
        resp = client.post("/api/positions/999/lots", json={
            "quantity": 30,
            "cost_basis": 195.0,
            "purchase_date": "2026-01-15",
        })
        assert resp.status_code == 404

    def test_update_notes(self, client):
        create_resp = client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 100,
            "cost_basis": 180.0,
            "purchase_date": "2025-06-01",
        })
        pid = create_resp.json()["id"]

        resp = client.put(f"/api/positions/{pid}", json={"notes": "Long-term hold"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Long-term hold"

    def test_update_nonexistent(self, client):
        resp = client.put("/api/positions/999", json={"notes": "test"})
        assert resp.status_code == 404

    def test_delete_position(self, client):
        create_resp = client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 100,
            "cost_basis": 180.0,
            "purchase_date": "2025-06-01",
        })
        pid = create_resp.json()["id"]

        resp = client.delete(f"/api/positions/{pid}")
        assert resp.status_code == 204

        resp = client.get(f"/api/positions/{pid}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/positions/999")
        assert resp.status_code == 404

    def test_tax_lot_response_includes_long_term_info(self, client):
        resp = client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 100,
            "cost_basis": 180.0,
            "purchase_date": "2024-01-01",
        })
        data = resp.json()
        lot = data["tax_lots"][0]
        assert lot["is_long_term"] is True
        assert lot["days_to_long_term"] == 0

    def test_list_positions_after_creates(self, client):
        client.post("/api/positions", json={
            "symbol": "AAPL", "quantity": 100, "cost_basis": 180.0, "purchase_date": "2025-06-01",
        })
        client.post("/api/positions", json={
            "symbol": "MSFT", "quantity": 50, "cost_basis": 300.0, "purchase_date": "2025-06-01",
        })
        resp = client.get("/api/positions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
