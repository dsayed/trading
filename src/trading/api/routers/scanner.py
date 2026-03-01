"""Scanner API router — discover opportunities across market universes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from trading.api.dependencies import get_config_repo, get_data_provider, get_scan_repo
from trading.api.schemas import (
    ScannerRequest,
    ScannerResponse,
    SignalResponse,
    UniverseResponse,
)
from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.core.factory import STRATEGIES, build_engine
from trading.core.repositories import ConfigRepo, ScanRepo
from trading.plugins.data._universes import SYMBOL_NAMES
from trading.plugins.data.base import DiscoveryProvider
from trading.plugins.data.cache import CachingDataProvider
from trading.plugins.data.composite import CompositeDataProvider

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

PREDEFINED_UNIVERSES = [
    "sp500", "nasdaq100", "dow30", "smallcap100", "forex_majors",
    "technology", "healthcare", "financials", "consumer_discretionary",
    "communication_services", "industrials", "consumer_staples",
    "energy", "utilities", "real_estate", "materials",
]
DYNAMIC_UNIVERSES = ["gainers", "losers", "most_active"]

# Providers that only support stock/equity data (no forex)
STOCKS_ONLY_PROVIDERS = {"marketdata"}

# Holding period presets: map to strategy constructor overrides
HOLDING_PERIOD_PRESETS: dict[str, dict[str, int]] = {
    "swing": {"short_window": 5, "long_window": 20, "lookback_days": 60},
    "position": {"short_window": 10, "long_window": 50, "lookback_days": 120},
    "longterm": {"short_window": 20, "long_window": 100, "lookback_days": 250},
}


def _build_engine_with_holding_period(
    config: TradingConfig,
    holding_period: str | None,
    data_provider: CachingDataProvider,
) -> TradingEngine:
    """Build engine with shared data provider, optionally overriding strategy params."""
    if not holding_period or holding_period not in HOLDING_PERIOD_PRESETS:
        return build_engine(config, data_provider=data_provider)

    preset = HOLDING_PERIOD_PRESETS[holding_period]

    import inspect
    from trading.core.factory import BROKERS, RISK_MANAGERS

    strategies = []
    for name in config.strategies:
        cls = STRATEGIES.get(name)
        if not cls:
            continue
        sig = inspect.signature(cls.__init__)
        kwargs: dict[str, object] = {}
        if "short_window" in sig.parameters:
            kwargs["short_window"] = preset["short_window"]
        if "long_window" in sig.parameters:
            kwargs["long_window"] = preset["long_window"]
        if "data_provider" in sig.parameters:
            kwargs["data_provider"] = data_provider
        strategies.append(cls(**kwargs))

    risk_manager = RISK_MANAGERS[config.risk_manager](
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
    )
    broker = BROKERS[config.broker]()

    return TradingEngine(
        data_provider=data_provider,
        strategies=strategies,
        risk_manager=risk_manager,
        broker=broker,
        config=config,
    )


def _compute_risk_reward(order) -> tuple[float | None, float | None, float | None]:
    """Compute position_value, risk_amount, reward_amount from an order."""
    entry = order.limit_price
    stop = order.stop_price
    qty = order.quantity
    if entry and stop and qty:
        position_value = round(qty * entry, 2)
        risk_amount = round(qty * abs(entry - stop), 2)
        reward_amount = risk_amount  # 1:1 R/R target
        return position_value, risk_amount, reward_amount
    return None, None, None


def _result_to_signal(result: dict) -> SignalResponse:
    signal = result["signal"]
    order = result["order"]
    sym = signal.instrument.symbol
    pos_val, risk, reward = _compute_risk_reward(order)
    return SignalResponse(
        symbol=sym,
        company_name=SYMBOL_NAMES.get(sym),
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
        position_value=pos_val,
        risk_amount=risk,
        reward_amount=reward,
    )


def _results_to_serializable(results: list[dict]) -> list[dict]:
    serialized = []
    for r in results:
        pos_val, risk, reward = _compute_risk_reward(r["order"])
        serialized.append({
            "symbol": r["signal"].instrument.symbol,
            "company_name": SYMBOL_NAMES.get(r["signal"].instrument.symbol),
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
            "position_value": pos_val,
            "risk_amount": risk,
            "reward_amount": reward,
        })
    return serialized


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

    # Validate forex + stocks-only provider mismatch
    # Allow if a forex_provider override is configured (CompositeDataProvider routes it)
    has_forex_override = (
        isinstance(raw_provider, CompositeDataProvider)
        and raw_provider.supports_forex
    )
    if (
        body.universe.lower() == "forex_majors"
        and provider_name in STOCKS_ONLY_PROVIDERS
        and not has_forex_override
    ):
        raise HTTPException(
            status_code=400,
            detail=f"'{provider_name}' is a stocks-only provider and cannot fetch forex data. "
                   f"Switch your primary provider to one that supports forex "
                   f"(polygon, twelvedata, yahoo), set a Forex Provider override in Settings, "
                   f"or choose a different universe.",
        )

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
    shared_provider: CachingDataProvider = Depends(get_data_provider),
) -> ScannerResponse:
    config = config_repo.get()
    engine = _build_engine_with_holding_period(config, body.holding_period, shared_provider)
    symbols, universe_label = _resolve_symbols(body, engine, config.data_provider)

    # Holding period can override lookback_days
    lookback = body.lookback_days
    if body.holding_period and body.holding_period in HOLDING_PERIOD_PRESETS:
        lookback = HOLDING_PERIOD_PRESETS[body.holding_period]["lookback_days"]

    results = await asyncio.to_thread(
        engine.discover,
        symbols,
        body.strategies,
        lookback,
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
    shared_provider: CachingDataProvider = Depends(get_data_provider),
) -> StreamingResponse:
    """SSE endpoint — streams progress events then the final result."""
    config = config_repo.get()
    engine = _build_engine_with_holding_period(config, body.holding_period, shared_provider)
    symbols, universe_label = _resolve_symbols(body, engine, config.data_provider)

    # Holding period can override lookback_days
    lookback = body.lookback_days
    if body.holding_period and body.holding_period in HOLDING_PERIOD_PRESETS:
        lookback = HOLDING_PERIOD_PRESETS[body.holding_period]["lookback_days"]

    progress_queue: asyncio.Queue[str | None] = asyncio.Queue()

    def on_progress(msg: str) -> None:
        progress_queue.put_nowait(msg)

    # Emit initial provider info so users see which provider is active
    provider_label = config.data_provider
    overrides = []
    if config.discovery_provider:
        overrides.append(f"discovery: {config.discovery_provider}")
    if config.forex_provider:
        overrides.append(f"forex: {config.forex_provider}")
    if overrides:
        provider_label += f" ({', '.join(overrides)})"
    on_progress(
        f"Provider: {provider_label} | "
        f"Universe: {universe_label} | "
        f"Symbols: {len(symbols)}"
    )

    async def run_in_background() -> list[dict]:
        try:
            results = await asyncio.to_thread(
                engine.discover,
                symbols,
                body.strategies,
                lookback,
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
