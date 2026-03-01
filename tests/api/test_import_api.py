"""Tests for the import API endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from trading.api.app import create_app
from trading.api.dependencies import get_database
from trading.core.database import Database


FIDELITY_CSV = (
    "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Current Value,Cost Basis Total\n"
    "Z12345678,INDIVIDUAL,AAPL,APPLE INC,100,190.50,19050.00,15025.00\n"
    "Z12345678,INDIVIDUAL,MSFT,MICROSOFT CORP,50,380.00,19000.00,14500.00\n"
    "Z12345678,INDIVIDUAL,FCASH,FIDELITY CASH,1000,1.00,1000.00,1000.00\n"
)

GENERIC_CSV = (
    "Symbol,Quantity,Cost Basis\n"
    "GOOG,10,140.50\n"
)


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "test.db")
    app = create_app()
    app.dependency_overrides[get_database] = lambda: db
    return TestClient(app)


class TestImportPreview:
    def test_preview_fidelity_csv(self, client):
        resp = client.post(
            "/api/import/preview",
            files={"file": ("positions.csv", FIDELITY_CSV, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_detected"] == "Fidelity"
        assert data["summary"]["total"] == 2  # FCASH skipped
        assert data["summary"]["new"] == 2
        assert data["summary"]["duplicates"] == 0

    def test_preview_detects_duplicates(self, client):
        # First create a position
        client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 50,
            "cost_basis": 160.00,
            "purchase_date": "2025-01-01",
        })

        # Then upload CSV containing AAPL
        resp = client.post(
            "/api/import/preview",
            files={"file": ("positions.csv", FIDELITY_CSV, "text/csv")},
        )
        data = resp.json()
        assert data["summary"]["duplicates"] == 1
        aapl = next(p for p in data["positions"] if p["symbol"] == "AAPL")
        assert aapl["status"] == "duplicate"

    def test_preview_rejects_non_csv(self, client):
        resp = client.post(
            "/api/import/preview",
            files={"file": ("data.txt", "not csv", "text/plain")},
        )
        assert resp.status_code == 400

    def test_preview_unrecognized_format(self, client):
        bad_csv = "Date,Weather\n2024-01-01,Sunny\n"
        resp = client.post(
            "/api/import/preview",
            files={"file": ("data.csv", bad_csv, "text/csv")},
        )
        assert resp.status_code == 400

    def test_preview_generic_csv(self, client):
        resp = client.post(
            "/api/import/preview",
            files={"file": ("positions.csv", GENERIC_CSV, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_detected"] == "Generic CSV"
        assert data["summary"]["total"] == 1


class TestImportCommit:
    def test_commit_creates_positions(self, client):
        resp = client.post("/api/import/commit", json={
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "cost_basis": 150.25,
                    "purchase_date": "2026-02-28",
                    "asset_class": "equity",
                    "status": "new",
                    "warnings": [],
                },
                {
                    "symbol": "MSFT",
                    "quantity": 50,
                    "cost_basis": 290.00,
                    "purchase_date": "2026-02-28",
                    "asset_class": "equity",
                    "status": "new",
                    "warnings": [],
                },
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2

        # Verify positions exist
        positions_resp = client.get("/api/positions")
        symbols = [p["symbol"] for p in positions_resp.json()]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_commit_duplicate_adds_tax_lot(self, client):
        # Create existing position
        client.post("/api/positions", json={
            "symbol": "AAPL",
            "quantity": 50,
            "cost_basis": 160.00,
            "purchase_date": "2025-01-01",
        })

        # Import another lot
        resp = client.post("/api/import/commit", json={
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "cost_basis": 150.25,
                    "purchase_date": "2026-02-28",
                    "asset_class": "equity",
                    "status": "duplicate",
                    "warnings": [],
                },
            ]
        })
        assert resp.status_code == 200

        # Verify position has 2 tax lots
        positions_resp = client.get("/api/positions")
        aapl = next(p for p in positions_resp.json() if p["symbol"] == "AAPL")
        assert len(aapl["tax_lots"]) == 2
        assert aapl["total_quantity"] == 150
