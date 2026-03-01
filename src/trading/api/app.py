"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from trading.api.routers import advise, config, diagnostics, import_positions, positions, scanner, scans, watchlists


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Dashboard", version="0.1.0")

    app.include_router(config.router)
    app.include_router(watchlists.router)
    app.include_router(scans.router)
    app.include_router(positions.router)
    app.include_router(advise.router)
    app.include_router(scanner.router)
    app.include_router(import_positions.router)
    app.include_router(diagnostics.router)

    # Serve React build in production (if it exists)
    dashboard_dir = Path(__file__).resolve().parent.parent.parent.parent / "dashboard" / "dist"
    if dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")

    return app


app = create_app()
