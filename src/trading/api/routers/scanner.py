"""Scanner API router — discover opportunities across market universes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from trading.api.dependencies import get_config_repo, get_scan_repo
from trading.api.schemas import (
    ScannerRequest,
    ScannerResponse,
    SignalResponse,
    UniverseResponse,
)
from trading.core.engine import TradingEngine
from trading.core.factory import build_engine
from trading.core.repositories import ConfigRepo, ScanRepo
from trading.plugins.data.base import DiscoveryProvider
from trading.plugins.data.cache import CachingDataProvider
from trading.plugins.data.composite import CompositeDataProvider

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

PREDEFINED_UNIVERSES = ["sp500", "nasdaq100", "forex_majors"]
DYNAMIC_UNIVERSES = ["gainers", "losers", "most_active"]


def _result_to_signal(result: dict) -> SignalResponse:
    signal = result["signal"]
    order = result["order"]
    return SignalResponse(
        symbol=signal.instrument.symbol,
        direction=signal.direction.value,
        conviction=signal.conviction,
        rationale=signal.rationale,
        strategy_name=signal.strategy_name,
        quantity=order.quantity,
        order_type=order.order_type.value,
        limit_price=order.limit_price,
        stop_price=order.stop_price,
        order_rationale=order.rationale,
        playbook=result["playbook"],
    )


def _results_to_serializable(results: list[dict]) -> list[dict]:
    return [
        {
            "symbol": r["signal"].instrument.symbol,
            "direction": r["signal"].direction.value,
            "conviction": r["signal"].conviction,
            "rationale": r["signal"].rationale,
            "strategy_name": r["signal"].strategy_name,
            "quantity": r["order"].quantity,
            "order_type": r["order"].order_type.value,
            "limit_price": r["order"].limit_price,
            "stop_price": r["order"].stop_price,
            "order_rationale": r["order"].rationale,
            "playbook": r["playbook"],
        }
        for r in results
    ]


def _resolve_symbols(
    body: ScannerRequest,
    engine: TradingEngine,
    provider_name: str,
) -> tuple[list[str], str]:
    """Resolve universe/symbols from request. Returns (symbols, universe_label)."""
    # Peek through cache wrapper
    raw_provider = engine.data_provider
    if isinstance(raw_provider, CachingDataProvider):
        raw_provider = raw_provider._inner

    if body.symbols:
        return body.symbols, "custom"

    if not body.universe:
        raise HTTPException(status_code=422, detail="Provide universe or symbols")

    # Check discovery support — CompositeDataProvider has explicit flag,
    # otherwise fall back to protocol isinstance check
    has_discovery = False
    if isinstance(raw_provider, CompositeDataProvider):
        has_discovery = raw_provider.supports_discovery
    elif isinstance(raw_provider, DiscoveryProvider):
        has_discovery = True

    if not has_discovery:
        raise HTTPException(
            status_code=400,
            detail=f"Data provider '{provider_name}' does not support "
                   f"universe discovery. Configure a discovery provider "
                   f"(polygon or fmp) in Settings, or provide symbols directly.",
        )

    name = body.universe.lower()
    if name in PREDEFINED_UNIVERSES:
        symbols = engine.data_provider.list_universe(name)
    elif name in ("gainers", "losers"):
        movers = engine.data_provider.get_movers(name, limit=body.max_results)
        symbols = [m["symbol"] for m in movers]
    elif name == "most_active":
        movers = engine.data_provider.get_movers("gainers", limit=body.max_results * 2)
        symbols = [m["symbol"] for m in movers][:body.max_results]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown universe: {name}")

    if not symbols:
        raise HTTPException(
            status_code=404, detail=f"No symbols found for universe '{name}'"
        )

    return symbols, body.universe


@router.get("/universes", response_model=UniverseResponse)
async def list_universes() -> UniverseResponse:
    return UniverseResponse(
        predefined=PREDEFINED_UNIVERSES,
        dynamic=DYNAMIC_UNIVERSES,
    )


@router.post("/run", response_model=ScannerResponse, status_code=201)
async def run_scanner(
    body: ScannerRequest,
    config_repo: ConfigRepo = Depends(get_config_repo),
    scan_repo: ScanRepo = Depends(get_scan_repo),
) -> ScannerResponse:
    config = config_repo.get()
    engine = build_engine(config)
    symbols, universe_label = _resolve_symbols(body, engine, config.data_provider)

    results = await asyncio.to_thread(
        engine.discover,
        symbols,
        body.strategies,
        body.lookback_days,
        body.max_results,
    )

    serializable = _results_to_serializable(results)
    record = scan_repo.save(
        symbols=symbols,
        results=serializable,
        watchlist_name=f"scanner:{universe_label}",
    )

    return ScannerResponse(
        id=record.id,
        ran_at=record.ran_at,
        signal_count=record.signal_count,
        universe=universe_label,
        signals=[_result_to_signal(r) for r in results],
    )


@router.post("/run-stream")
async def run_scanner_stream(
    body: ScannerRequest,
    request: Request,
    config_repo: ConfigRepo = Depends(get_config_repo),
    scan_repo: ScanRepo = Depends(get_scan_repo),
) -> StreamingResponse:
    """SSE endpoint — streams progress events then the final result."""
    config = config_repo.get()
    engine = build_engine(config)
    symbols, universe_label = _resolve_symbols(body, engine, config.data_provider)

    progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_progress(msg: str) -> None:
        progress_queue.put_nowait(msg)

    async def run_in_background() -> list[dict]:
        try:
            results = await asyncio.to_thread(
                engine.discover,
                symbols,
                body.strategies,
                body.lookback_days,
                body.max_results,
                on_progress,
            )
            return results
        finally:
            await progress_queue.put(None)  # sentinel

    async def event_stream() -> AsyncGenerator[str, None]:
        task = asyncio.create_task(run_in_background())

        # Stream progress events
        while True:
            if await request.is_disconnected():
                task.cancel()
                return
            msg = await progress_queue.get()
            if msg is None:
                break
            yield f"event: progress\ndata: {json.dumps({'message': msg})}\n\n"

        # Get final result
        results = await task
        serializable = _results_to_serializable(results)
        record = scan_repo.save(
            symbols=symbols,
            results=serializable,
            watchlist_name=f"scanner:{universe_label}",
        )

        response_data = ScannerResponse(
            id=record.id,
            ran_at=record.ran_at,
            signal_count=record.signal_count,
            universe=universe_label,
            signals=[_result_to_signal(r) for r in results],
        )
        yield f"event: result\ndata: {response_data.model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
