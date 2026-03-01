"""Config API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from trading.api.dependencies import get_config_repo, invalidate_data_provider
from trading.api.schemas import ConfigResponse, ConfigUpdateRequest
from trading.core.config import TradingConfig
from trading.core.repositories import ConfigRepo

router = APIRouter(prefix="/api/config", tags=["config"])


def _mask_api_key(key: str | None) -> tuple[bool, str]:
    """Return (is_set, hint) for an API key without exposing the full value."""
    if not key:
        return False, ""
    if len(key) <= 8:
        return True, "****"
    return True, f"{key[:4]}****{key[-4:]}"


def _to_response(config: TradingConfig) -> ConfigResponse:
    poly_set, poly_hint = _mask_api_key(config.polygon_api_key)
    fmp_set, fmp_hint = _mask_api_key(config.fmp_api_key)
    md_set, md_hint = _mask_api_key(config.marketdata_api_key)
    td_set, td_hint = _mask_api_key(config.twelvedata_api_key)
    return ConfigResponse(
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
        data_provider=config.data_provider,
        strategies=config.strategies,
        risk_manager=config.risk_manager,
        broker=config.broker,
        polygon_api_key_set=poly_set,
        polygon_api_key_hint=poly_hint,
        options_provider=config.options_provider,
        discovery_provider=config.discovery_provider,
        forex_provider=config.forex_provider,
        fmp_api_key_set=fmp_set,
        fmp_api_key_hint=fmp_hint,
        marketdata_api_key_set=md_set,
        marketdata_api_key_hint=md_hint,
        twelvedata_api_key_set=td_set,
        twelvedata_api_key_hint=td_hint,
    )


@router.get("", response_model=ConfigResponse)
async def get_config(repo: ConfigRepo = Depends(get_config_repo)) -> ConfigResponse:
    return _to_response(repo.get())


_PROVIDER_FIELDS = {
    "data_provider", "options_provider", "discovery_provider", "forex_provider",
    "polygon_api_key", "fmp_api_key", "marketdata_api_key", "twelvedata_api_key",
}


@router.put("", response_model=ConfigResponse)
async def update_config(
    body: ConfigUpdateRequest,
    repo: ConfigRepo = Depends(get_config_repo),
) -> ConfigResponse:
    updates = body.model_dump(exclude_none=True)
    config = repo.update(**updates)
    # Invalidate cached data provider if any provider-related field changed
    if updates.keys() & _PROVIDER_FIELDS:
        invalidate_data_provider()
    return _to_response(config)
