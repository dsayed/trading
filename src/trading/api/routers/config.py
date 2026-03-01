"""Config API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from trading.api.dependencies import get_config_repo
from trading.api.schemas import ConfigResponse, ConfigUpdateRequest
from trading.core.repositories import ConfigRepo

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(repo: ConfigRepo = Depends(get_config_repo)) -> ConfigResponse:
    config = repo.get()
    return ConfigResponse(
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
        data_provider=config.data_provider,
        strategies=config.strategies,
        risk_manager=config.risk_manager,
        broker=config.broker,
    )


@router.put("", response_model=ConfigResponse)
async def update_config(
    body: ConfigUpdateRequest,
    repo: ConfigRepo = Depends(get_config_repo),
) -> ConfigResponse:
    config = repo.update(**body.model_dump(exclude_none=True))
    return ConfigResponse(
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
        data_provider=config.data_provider,
        strategies=config.strategies,
        risk_manager=config.risk_manager,
        broker=config.broker,
    )
