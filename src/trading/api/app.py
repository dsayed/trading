"""FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from trading.api.auth import require_api_key
from trading.api.routers import advise, config, diagnostics, import_positions, positions, scanner, scans, watchlists


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Dashboard", version="0.1.0")

    # All API routes require a valid API key (skipped automatically in dev when
    # SUPABASE_DB_URL is not set — see trading/api/auth.py)
    auth = [Depends(require_api_key)]

    app.include_router(config.router, dependencies=auth)
    app.include_router(watchlists.router, dependencies=auth)
    app.include_router(scans.router, dependencies=auth)
    app.include_router(positions.router, dependencies=auth)
    app.include_router(advise.router, dependencies=auth)
    app.include_router(scanner.router, dependencies=auth)
    app.include_router(import_positions.router, dependencies=auth)
    # Diagnostics is public — used by health checks and monitoring
    app.include_router(diagnostics.router)

    # Serve React build in production (if it exists)
    dashboard_dir = Path(__file__).resolve().parent.parent.parent.parent / "dashboard" / "dist"
    if dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")

    return app


app = create_app()
