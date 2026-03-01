"""Advise API router — runs advisor pipeline on positions."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from trading.api.dependencies import get_config_repo, get_position_repo
from trading.api.schemas import (
    AdviseRequest,
    AdviseResponse,
    OptionContractResponse,
    PlayResponse,
    PositionAdviceResponse,
)
from trading.core.factory import build_advisors, build_engine
from trading.core.repositories import ConfigRepo, PositionRepo

router = APIRouter(prefix="/api/advise", tags=["advise"])


def _play_to_response(play: object) -> PlayResponse:
    """Convert a domain Play to PlayResponse."""
    oc = None
    if play.option_contract is not None:  # type: ignore[union-attr]
        c = play.option_contract  # type: ignore[union-attr]
        oc = OptionContractResponse(
            contract_symbol=c.contract_symbol,
            strike=c.strike,
            expiration=c.expiration.isoformat(),
            option_type=c.option_type,
            bid=c.bid,
            ask=c.ask,
            mid_price=c.mid_price,
            volume=c.volume,
            open_interest=c.open_interest,
            implied_volatility=c.implied_volatility,
        )
    return PlayResponse(
        play_type=play.play_type.value,  # type: ignore[union-attr]
        title=play.title,  # type: ignore[union-attr]
        rationale=play.rationale,  # type: ignore[union-attr]
        conviction=play.conviction,  # type: ignore[union-attr]
        option_contract=oc,
        contracts=play.contracts,  # type: ignore[union-attr]
        premium=play.premium,  # type: ignore[union-attr]
        max_profit=play.max_profit,  # type: ignore[union-attr]
        max_loss=play.max_loss,  # type: ignore[union-attr]
        breakeven=play.breakeven,  # type: ignore[union-attr]
        tax_note=play.tax_note,  # type: ignore[union-attr]
        playbook=play.playbook,  # type: ignore[union-attr]
        advisor_name=play.advisor_name,  # type: ignore[union-attr]
    )


@router.post("", response_model=AdviseResponse)
async def run_advise(
    body: AdviseRequest,
    config_repo: ConfigRepo = Depends(get_config_repo),
    position_repo: PositionRepo = Depends(get_position_repo),
) -> AdviseResponse:
    # Load positions
    if body.position_ids:
        records = []
        for pid in body.position_ids:
            rec = position_repo.get(pid)
            if rec is None:
                raise HTTPException(
                    status_code=404, detail=f"Position {pid} not found"
                )
            records.append(rec)
    else:
        records = position_repo.list_all()

    if not records:
        raise HTTPException(status_code=422, detail="No positions found")

    # Convert to domain models
    positions = [position_repo.to_domain(r) for r in records]

    # Build engine and advisors
    config = config_repo.get()
    engine = build_engine(config)
    advisors = build_advisors(body.advisor_names)

    if not advisors:
        raise HTTPException(status_code=422, detail="No valid advisors specified")

    # Run advise in thread pool
    results = await asyncio.to_thread(
        engine.advise, positions, advisors, body.lookback_days
    )

    # Build response
    position_responses = []
    for result in results:
        pos = result["position"]
        position_responses.append(
            PositionAdviceResponse(
                symbol=pos.instrument.symbol,
                current_price=result["current_price"],
                unrealized_pnl=result["unrealized_pnl"],
                total_quantity=pos.total_quantity,
                average_cost=pos.average_cost,
                plays=[_play_to_response(p) for p in result["plays"]],
            )
        )

    return AdviseResponse(positions=position_responses)
