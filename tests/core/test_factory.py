"""Tests for the shared engine factory."""

from trading.core.config import TradingConfig
from trading.core.engine import TradingEngine
from trading.core.factory import build_advisors, build_engine


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
