"""Tests for the shared engine factory."""

from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.core.factory import build_advisors, build_engine
from trading.plugins.data.cache import CachingDataProvider
from trading.plugins.data.composite import CompositeDataProvider
from trading.plugins.strategies.intermarket import IntermarketStrategy


class TestBuildEngine:
    def test_returns_trading_engine(self):
        config = TradingConfig(watchlist=["AAPL"])
        engine = build_engine(config)
        assert isinstance(engine, TradingEngine)

    def test_resolves_strategy_names(self):
        config = TradingConfig(strategies=["momentum"])
        engine = build_engine(config)
        assert len(engine.strategies) == 1
        assert engine.strategies[0].name == "momentum"

    def test_skips_unknown_strategies(self):
        config = TradingConfig(strategies=["momentum", "nonexistent"])
        engine = build_engine(config)
        assert len(engine.strategies) == 1

    def test_passes_config_to_risk_manager(self):
        config = TradingConfig(stake=5000, max_position_pct=0.25, stop_loss_pct=0.03)
        engine = build_engine(config)
        assert engine.risk_manager.stake == 5000
        assert engine.risk_manager.max_position_pct == 0.25
        assert engine.risk_manager.stop_loss_pct == 0.03

    def test_uses_config_watchlist(self):
        config = TradingConfig(watchlist=["AAPL", "MSFT"])
        engine = build_engine(config)
        assert engine.config.watchlist == ["AAPL", "MSFT"]

    def test_cash_defaults_to_stake(self):
        config = TradingConfig(stake=7500)
        engine = build_engine(config)
        assert engine.cash == 7500


class TestBuildEngineComposite:
    def test_no_overrides_uses_single_provider(self):
        config = TradingConfig(watchlist=["AAPL"])
        engine = build_engine(config)
        # No composite — just CachingDataProvider wrapping the single provider
        assert isinstance(engine.data_provider, CachingDataProvider)
        assert not isinstance(engine.data_provider._inner, CompositeDataProvider)

    def test_options_override_creates_composite(self, monkeypatch):
        monkeypatch.setenv("MARKETDATA_API_KEY", "test-key")
        config = TradingConfig(
            watchlist=["AAPL"],
            options_provider="marketdata",
            marketdata_api_key="test-key",
        )
        engine = build_engine(config)
        inner = engine.data_provider._inner
        assert isinstance(inner, CompositeDataProvider)
        assert inner.supports_options is True

    def test_discovery_override_creates_composite(self, monkeypatch):
        monkeypatch.setenv("FMP_API_KEY", "test-key")
        config = TradingConfig(
            watchlist=["AAPL"],
            discovery_provider="fmp",
            fmp_api_key="test-key",
        )
        engine = build_engine(config)
        inner = engine.data_provider._inner
        assert isinstance(inner, CompositeDataProvider)
        assert inner.supports_discovery is True

    def test_composite_name_concatenates(self, monkeypatch):
        monkeypatch.setenv("FMP_API_KEY", "test-key")
        monkeypatch.setenv("MARKETDATA_API_KEY", "test-key")
        config = TradingConfig(
            watchlist=["AAPL"],
            options_provider="marketdata",
            discovery_provider="fmp",
            marketdata_api_key="test-key",
            fmp_api_key="test-key",
        )
        engine = build_engine(config)
        inner = engine.data_provider._inner
        assert "yahoo" in inner.name
        assert "marketdata" in inner.name
        assert "fmp" in inner.name


class TestBuildAdvisors:
    def test_returns_all_advisors_by_default(self):
        advisors = build_advisors()
        assert len(advisors) == 3
        names = {a.name for a in advisors}
        assert "stock_play" in names
        assert "covered_call" in names
        assert "protective_put" in names

    def test_filters_by_name(self):
        advisors = build_advisors(["stock_play", "covered_call"])
        assert len(advisors) == 2
        names = {a.name for a in advisors}
        assert "stock_play" in names
        assert "covered_call" in names

    def test_skips_unknown_names(self):
        advisors = build_advisors(["stock_play", "nonexistent"])
        assert len(advisors) == 1
        assert advisors[0].name == "stock_play"

    def test_empty_list_returns_empty(self):
        advisors = build_advisors([])
        assert len(advisors) == 0


class TestIntermarketWiring:
    def test_intermarket_strategy_receives_data_provider(self):
        config = TradingConfig(strategies=["intermarket"])
        engine = build_engine(config)
        assert len(engine.strategies) == 1
        strategy = engine.strategies[0]
        assert isinstance(strategy, IntermarketStrategy)
        assert strategy._data_provider is engine.data_provider

    def test_non_intermarket_strategies_unaffected(self):
        config = TradingConfig(strategies=["momentum", "intermarket"])
        engine = build_engine(config)
        assert len(engine.strategies) == 2
        assert engine.strategies[0].name == "momentum"
        assert engine.strategies[1].name == "intermarket"
