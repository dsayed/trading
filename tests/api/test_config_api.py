"""Tests for the config API endpoints."""

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


class TestConfigAPI:
    def test_get_returns_defaults(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stake"] == 10_000
        assert data["strategies"] == ["momentum"]
        assert data["broker"] == "manual"

    def test_put_updates_fields(self, client):
        resp = client.put("/api/config", json={"stake": 5000})
        assert resp.status_code == 200
        assert resp.json()["stake"] == 5000

    def test_put_partial_preserves_other_fields(self, client):
        client.put("/api/config", json={"stake": 5000})
        resp = client.put("/api/config", json={"stop_loss_pct": 0.03})
        data = resp.json()
        assert data["stake"] == 5000  # unchanged
        assert data["stop_loss_pct"] == 0.03  # updated

    def test_get_reflects_updates(self, client):
        client.put("/api/config", json={"stake": 7500})
        resp = client.get("/api/config")
        assert resp.json()["stake"] == 7500
