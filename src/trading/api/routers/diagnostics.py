"""Diagnostics API router — health checks and provider connectivity tests."""

from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from trading.api.dependencies import get_config_repo
from trading.core.factory import _build_provider
from trading.core.models import AssetClass, Instrument
from trading.core.repositories import ConfigRepo

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


class HealthResponse(BaseModel):
    status: str


class ProviderStatus(BaseModel):
    name: str
    role: str
    ok: bool
    latency_ms: float
    bars_returned: int
    error: str | None = None


class DiagnosticsResponse(BaseModel):
    providers: list[ProviderStatus]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _test_provider(name: str, role: str, config) -> ProviderStatus:
    """Probe a provider by fetching 5 days of AAPL bars."""
    end = date.today()
    start = end - timedelta(days=5)
    instrument = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)

    t0 = time.monotonic()
    try:
        provider = _build_provider(name, config)
        bars = provider.fetch_bars(instrument, start, end)
        elapsed = (time.monotonic() - t0) * 1000
        return ProviderStatus(
            name=name,
            role=role,
            ok=True,
            latency_ms=round(elapsed, 1),
            bars_returned=len(bars),
        )
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return ProviderStatus(
            name=name,
            role=role,
            ok=False,
            latency_ms=round(elapsed, 1),
            bars_returned=0,
            error=str(exc),
        )


@router.get("/providers", response_model=DiagnosticsResponse)
async def test_providers(
    config_repo: ConfigRepo = Depends(get_config_repo),
) -> DiagnosticsResponse:
    """Test each active provider by fetching 5 days of AAPL bars."""
    config = config_repo.get()

    # Collect unique (provider_name, role) pairs
    tests: list[tuple[str, str]] = [
        (config.data_provider, "bars"),
    ]
    if config.options_provider:
        tests.append((config.options_provider, "options"))
    if config.discovery_provider:
        tests.append((config.discovery_provider, "discovery"))
    if config.forex_provider:
        tests.append((config.forex_provider, "forex"))

    # Deduplicate by provider name (keep first role)
    seen: set[str] = set()
    unique_tests: list[tuple[str, str]] = []
    for name, role in tests:
        if name not in seen:
            seen.add(name)
            unique_tests.append((name, role))

    results = await asyncio.gather(
        *[asyncio.to_thread(_test_provider, name, role, config) for name, role in unique_tests]
    )

    return DiagnosticsResponse(providers=list(results))
