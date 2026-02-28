from pathlib import Path

import pytest

from trading.core.config import TradingConfig, load_config


class TestTradingConfig:
    def test_default_config(self):
        config = TradingConfig()
        assert config.stake == 10_000
        assert config.data_provider == "yahoo"
        assert config.strategies == ["momentum"]
        assert config.risk_manager == "fixed_stake"
        assert config.broker == "manual"

    def test_custom_config(self):
        config = TradingConfig(
            stake=5_000,
            strategies=["momentum", "mean_reversion"],
            watchlist=["AAPL", "MSFT", "GOOG"],
        )
        assert config.stake == 5_000
        assert len(config.strategies) == 2
        assert config.watchlist == ["AAPL", "MSFT", "GOOG"]


class TestLoadConfig:
    def test_load_from_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[trading]\n'
            'stake = 5000\n'
            'watchlist = ["AAPL", "GOOG"]\n'
            'strategies = ["momentum"]\n'
        )
        config = load_config(config_file)
        assert config.stake == 5_000
        assert config.watchlist == ["AAPL", "GOOG"]

    def test_load_defaults_when_no_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.stake == 10_000

    def test_watchlist_default_empty(self):
        config = TradingConfig()
        assert config.watchlist == []
