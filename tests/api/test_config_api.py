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

    def test_get_includes_new_provider_fields(self, client):
        resp = client.get("/api/config")
        data = resp.json()
        assert data["options_provider"] is None
        assert data["discovery_provider"] is None
        assert data["fmp_api_key_set"] is False
        assert data["marketdata_api_key_set"] is False
        assert data["twelvedata_api_key_set"] is False

    def test_put_updates_provider_overrides(self, client):
        resp = client.put("/api/config", json={
            "options_provider": "marketdata",
            "discovery_provider": "fmp",
        })
        data = resp.json()
        assert data["options_provider"] == "marketdata"
        assert data["discovery_provider"] == "fmp"

    def test_put_masks_fmp_api_key(self, client):
        client.put("/api/config", json={"fmp_api_key": "abcd1234efgh5678"})
        resp = client.get("/api/config")
        data = resp.json()
        assert data["fmp_api_key_set"] is True
        assert data["fmp_api_key_hint"] == "abcd****5678"

    def test_put_masks_marketdata_api_key(self, client):
        client.put("/api/config", json={"marketdata_api_key": "mk_test_key_value"})
        resp = client.get("/api/config")
        data = resp.json()
        assert data["marketdata_api_key_set"] is True
        assert "****" in data["marketdata_api_key_hint"]

    def test_put_masks_twelvedata_api_key(self, client):
        client.put("/api/config", json={"twelvedata_api_key": "td_abcdefghij"})
        resp = client.get("/api/config")
        data = resp.json()
        assert data["twelvedata_api_key_set"] is True
        assert "****" in data["twelvedata_api_key_hint"]
