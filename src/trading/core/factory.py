"""Shared engine construction for CLI and API."""

from __future__ import annotations

from typing import Any

from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.plugins.advisors.covered_call import CoveredCallAdvisor
from trading.plugins.advisors.protective_put import ProtectivePutAdvisor
from trading.plugins.advisors.stock_play import StockPlayAdvisor
from trading.plugins.brokers.manual import ManualBroker
from trading.plugins.data.yahoo import YahooFinanceProvider
from trading.plugins.risk.fixed_stake import FixedStakeRiskManager
from trading.plugins.strategies.momentum import MomentumStrategy

# Plugin registries — maps config string names to implementation classes
DATA_PROVIDERS = {"yahoo": YahooFinanceProvider}
STRATEGIES = {"momentum": MomentumStrategy}
RISK_MANAGERS = {"fixed_stake": FixedStakeRiskManager}
BROKERS = {"manual": ManualBroker}
ADVISORS: dict[str, type] = {
    "stock_play": StockPlayAdvisor,
    "covered_call": CoveredCallAdvisor,
    "protective_put": ProtectivePutAdvisor,
}


def build_engine(config: TradingConfig) -> TradingEngine:
    """Build a TradingEngine from config, resolving plugin names to implementations."""
    data_provider = DATA_PROVIDERS[config.data_provider]()

    strategies = [
        STRATEGIES[name]() for name in config.strategies if name in STRATEGIES
    ]

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


def build_advisors(names: list[str] | None = None) -> list[Any]:
    """Build advisor instances by name. Defaults to all advisors if None."""
    if names is None:
        names = list(ADVISORS.keys())
    return [ADVISORS[n]() for n in names if n in ADVISORS]
