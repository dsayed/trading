"""Shared engine construction for CLI and API."""

from __future__ import annotations

import inspect
from typing import Any

from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.plugins.advisors.covered_call import CoveredCallAdvisor
from trading.plugins.advisors.protective_put import ProtectivePutAdvisor
from trading.plugins.advisors.stock_play import StockPlayAdvisor
from trading.plugins.brokers.manual import ManualBroker
from trading.plugins.data.base import OptionsDataProvider
from trading.plugins.data.cache import CachingDataProvider
from trading.plugins.data.composite import CompositeDataProvider
from trading.plugins.data.fmp import FMPProvider
from trading.plugins.data.marketdata import MarketDataProvider
from trading.plugins.data.polygon import PolygonProvider
from trading.plugins.data.twelvedata import TwelveDataProvider
from trading.plugins.data.yahoo import YahooFinanceProvider
from trading.plugins.risk.fixed_stake import FixedStakeRiskManager
from trading.plugins.strategies.income import IncomeStrategy
from trading.plugins.strategies.intermarket import IntermarketStrategy
from trading.plugins.strategies.macd_divergence import MACDDivergenceStrategy
from trading.plugins.strategies.mean_reversion import MeanReversionStrategy
from trading.plugins.strategies.momentum import MomentumStrategy

# Plugin registries — maps config string names to implementation classes
DATA_PROVIDERS: dict[str, type] = {
    "yahoo": YahooFinanceProvider,
    "polygon": PolygonProvider,
    "fmp": FMPProvider,
    "marketdata": MarketDataProvider,
    "twelvedata": TwelveDataProvider,
}
STRATEGIES: dict[str, type] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "income": IncomeStrategy,
    "macd_divergence": MACDDivergenceStrategy,
    "intermarket": IntermarketStrategy,
}
RISK_MANAGERS = {"fixed_stake": FixedStakeRiskManager}
BROKERS = {"manual": ManualBroker}
ADVISORS: dict[str, type] = {
    "stock_play": StockPlayAdvisor,
    "covered_call": CoveredCallAdvisor,
    "protective_put": ProtectivePutAdvisor,
}

# Maps provider names to the config field that holds their API key
_PROVIDER_KEY_FIELDS: dict[str, str] = {
    "polygon": "polygon_api_key",
    "fmp": "fmp_api_key",
    "marketdata": "marketdata_api_key",
    "twelvedata": "twelvedata_api_key",
}


def _build_provider(name: str, config: TradingConfig) -> Any:
    """Instantiate a single data provider by name, passing the right API key."""
    cls = DATA_PROVIDERS[name]
    key_field = _PROVIDER_KEY_FIELDS.get(name)
    if key_field:
        return cls(api_key=getattr(config, key_field))
    return cls()


def build_engine(config: TradingConfig) -> TradingEngine:
    """Build a TradingEngine from config, resolving plugin names to implementations."""
    bars_provider = _build_provider(config.data_provider, config)

    # Build composite if role overrides are configured
    if config.options_provider or config.discovery_provider or config.forex_provider:
        options = (
            _build_provider(config.options_provider, config)
            if config.options_provider
            else None
        )
        # If no explicit options override, and the bars provider supports options,
        # reuse it so options aren't silently lost when building a composite.
        if options is None and isinstance(bars_provider, OptionsDataProvider):
            options = bars_provider
        discovery = (
            _build_provider(config.discovery_provider, config)
            if config.discovery_provider
            else None
        )
        forex = (
            _build_provider(config.forex_provider, config)
            if config.forex_provider
            else None
        )
        raw_provider = CompositeDataProvider(
            bars_provider,
            options_provider=options,
            discovery_provider=discovery,
            forex_provider=forex,
        )
    else:
        raw_provider = bars_provider

    data_provider = CachingDataProvider(raw_provider)

    strategies = []
    for name in config.strategies:
        cls = STRATEGIES.get(name)
        if not cls:
            continue
        sig = inspect.signature(cls.__init__)
        kwargs: dict[str, Any] = {}
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


def build_advisors(names: list[str] | None = None) -> list[Any]:
    """Build advisor instances by name. Defaults to all advisors if None."""
    if names is None:
        names = list(ADVISORS.keys())
    return [ADVISORS[n]() for n in names if n in ADVISORS]
