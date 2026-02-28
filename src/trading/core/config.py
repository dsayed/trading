"""Configuration loading and validation."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TradingConfig(BaseModel):
    """Trading system configuration."""

    stake: float = 10_000
    max_position_pct: float = 0.40
    stop_loss_pct: float = 0.05
    data_provider: str = "yahoo"
    strategies: list[str] = Field(default_factory=lambda: ["momentum"])
    risk_manager: str = "fixed_stake"
    broker: str = "manual"
    watchlist: list[str] = Field(default_factory=list)


def load_config(path: Path) -> TradingConfig:
    """Load config from a TOML file. Returns defaults if file doesn't exist."""
    if not path.exists():
        return TradingConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    trading_data: dict[str, Any] = data.get("trading", {})
    return TradingConfig(**trading_data)
