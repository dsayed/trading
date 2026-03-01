"""Tests for the watchlist API endpoints."""

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


class TestWatchlistsAPI:
    def test_list_empty(self, client):
        resp = client.get("/api/watchlists")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create(self, client):
        resp = client.post(
            "/api/watchlists",
            json={"name": "Tech", "symbols": ["AAPL", "MSFT"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Tech"
        assert data["symbols"] == ["AAPL", "MSFT"]
        assert "id" in data

    def test_get(self, client):
        create_resp = client.post(
            "/api/watchlists", json={"name": "My List", "symbols": ["GOOG"]}
        )
        wl_id = create_resp.json()["id"]
        resp = client.get(f"/api/watchlists/{wl_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "My List"

    def test_update_name(self, client):
        create_resp = client.post(
            "/api/watchlists", json={"name": "Old", "symbols": ["AAPL"]}
        )
        wl_id = create_resp.json()["id"]
        resp = client.put(f"/api/watchlists/{wl_id}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"
        assert resp.json()["symbols"] == ["AAPL"]

    def test_update_symbols(self, client):
        create_resp = client.post(
            "/api/watchlists", json={"name": "List", "symbols": ["AAPL"]}
        )
        wl_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/watchlists/{wl_id}", json={"symbols": ["AAPL", "MSFT"]}
        )
        assert resp.status_code == 200
        assert resp.json()["symbols"] == ["AAPL", "MSFT"]

    def test_delete(self, client):
        create_resp = client.post(
            "/api/watchlists", json={"name": "ToDelete"}
        )
        wl_id = create_resp.json()["id"]
        resp = client.delete(f"/api/watchlists/{wl_id}")
        assert resp.status_code == 204

        resp = client.get(f"/api/watchlists/{wl_id}")
        assert resp.status_code == 404

    def test_get_nonexistent(self, client):
        resp = client.get("/api/watchlists/999")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/watchlists/999")
        assert resp.status_code == 404

    def test_list_returns_all(self, client):
        client.post("/api/watchlists", json={"name": "A"})
        client.post("/api/watchlists", json={"name": "B"})
        resp = client.get("/api/watchlists")
        assert len(resp.json()) == 2
