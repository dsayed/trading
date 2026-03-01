"""Tests for the diagnostics API endpoints."""

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


class TestHealthEndpoint:
    def test_returns_ok(self, client):
        resp = client.get("/api/diagnostics/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestProvidersEndpoint:
    def test_returns_provider_status(self, client):
        """Default config uses yahoo provider — should return a result for it."""
        resp = client.get("/api/diagnostics/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) >= 1

        provider = data["providers"][0]
        assert provider["name"] == "yahoo"
        assert provider["role"] == "bars"
        assert isinstance(provider["ok"], bool)
        assert isinstance(provider["latency_ms"], (int, float))
        assert "bars_returned" in provider

    def test_provider_has_error_field_on_failure(self, client):
        """Set up an invalid provider to test error reporting."""
        # Configure FMP without a valid key — should report error
        client.put("/api/config", json={
            "data_provider": "fmp",
            "fmp_api_key": "invalid-test-key",
        })
        resp = client.get("/api/diagnostics/providers")
        assert resp.status_code == 200
        data = resp.json()

        fmp = data["providers"][0]
        assert fmp["name"] == "fmp"
        # It will either succeed (if key works) or fail with an error
        assert isinstance(fmp["ok"], bool)
        if not fmp["ok"]:
            assert fmp["error"] is not None
