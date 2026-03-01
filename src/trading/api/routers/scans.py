"""Scan API router."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from trading.api.dependencies import get_config_repo, get_scan_repo, get_watchlist_repo
from trading.api.schemas import (
    ScanRequest,
    ScanResponse,
    ScanSummaryResponse,
    SignalResponse,
)
from trading.core.factory import build_engine
from trading.core.repositories import ConfigRepo, ScanRepo, WatchlistRepo

router = APIRouter(prefix="/api/scans", tags=["scans"])


def _result_to_signal(result: dict) -> SignalResponse:
    """Convert an engine scan result dict to a SignalResponse."""
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
    """Convert engine results to JSON-serializable dicts for DB storage."""
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


def _stored_to_signals(stored: list[dict]) -> list[SignalResponse]:
    """Convert stored JSON dicts back to SignalResponse objects."""
    return [SignalResponse(**item) for item in stored]


@router.post("", response_model=ScanResponse, status_code=201)
async def run_scan(
    body: ScanRequest,
    config_repo: ConfigRepo = Depends(get_config_repo),
    watchlist_repo: WatchlistRepo = Depends(get_watchlist_repo),
    scan_repo: ScanRepo = Depends(get_scan_repo),
) -> ScanResponse:
    # Resolve symbols
    watchlist_name: str | None = None
    if body.watchlist_id is not None:
        wl = watchlist_repo.get(body.watchlist_id)
        if wl is None:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        symbols = wl.symbols
        watchlist_name = wl.name
    elif body.symbols:
        symbols = body.symbols
    else:
        raise HTTPException(
            status_code=422, detail="Provide watchlist_id or symbols"
        )

    # Build engine from current DB config
    config = config_repo.get()
    config = config.model_copy(update={"watchlist": symbols})
    engine = build_engine(config)

    # Run scan in thread pool (engine is synchronous)
    results = await asyncio.to_thread(
        engine.scan, symbols, body.lookback_days
    )

    # Save to DB
    serializable = _results_to_serializable(results)
    record = scan_repo.save(
        symbols=symbols,
        results=serializable,
        watchlist_name=watchlist_name,
    )

    return ScanResponse(
        id=record.id,
        ran_at=record.ran_at,
        signal_count=record.signal_count,
        signals=[_result_to_signal(r) for r in results],
    )


@router.get("", response_model=list[ScanSummaryResponse])
async def list_scans(
    limit: int = 20,
    scan_repo: ScanRepo = Depends(get_scan_repo),
) -> list[ScanSummaryResponse]:
    summaries = scan_repo.list_recent(limit=limit)
    return [
        ScanSummaryResponse(
            id=s.id,
            ran_at=s.ran_at,
            watchlist_name=s.watchlist_name,
            symbols=s.symbols,
            signal_count=s.signal_count,
        )
        for s in summaries
    ]


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: int,
    scan_repo: ScanRepo = Depends(get_scan_repo),
) -> ScanResponse:
    record = scan_repo.get(scan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse(
        id=record.id,
        ran_at=record.ran_at,
        signal_count=record.signal_count,
        signals=_stored_to_signals(record.results),
    )
