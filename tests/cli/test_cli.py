from unittest.mock import patch

from typer.testing import CliRunner

from trading.cli.main import app

runner = CliRunner()


class TestCLIScan:
    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower() or "Scan" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_shows_output(self, mock_build):
        from datetime import datetime
        from trading.core.models import (
            AssetClass,
            Direction,
            Instrument,
            Order,
            OrderType,
            Signal,
        )

        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = [
            {
                "signal": Signal(
                    instrument=inst,
                    direction=Direction.LONG,
                    conviction=0.78,
                    rationale="Test rationale",
                    strategy_name="momentum",
                    timestamp=datetime(2026, 2, 28),
                ),
                "order": Order(
                    instrument=inst,
                    direction=Direction.LONG,
                    quantity=54,
                    order_type=OrderType.LIMIT,
                    limit_price=185.20,
                    stop_price=176.00,
                    rationale="54 shares",
                ),
                "playbook": "BUY 54 shares of AAPL at $185.20",
            }
        ]

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "AAPL" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_no_signals(self, mock_build):
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = []
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "No" in result.output

    @patch("trading.cli.main._build_engine")
    def test_scan_with_explain(self, mock_build):
        from datetime import datetime
        from trading.core.models import (
            AssetClass,
            Direction,
            Instrument,
            Order,
            OrderType,
            Signal,
        )

        inst = Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)
        mock_engine = mock_build.return_value
        mock_engine.scan.return_value = [
            {
                "signal": Signal(
                    instrument=inst,
                    direction=Direction.LONG,
                    conviction=0.78,
                    rationale="Detailed test rationale for AAPL",
                    strategy_name="momentum",
                    timestamp=datetime(2026, 2, 28),
                ),
                "order": Order(
                    instrument=inst,
                    direction=Direction.LONG,
                    quantity=54,
                    order_type=OrderType.LIMIT,
                    limit_price=185.20,
                    rationale="54 shares at $185.20",
                ),
                "playbook": "Full playbook here",
            }
        ]

        result = runner.invoke(app, ["scan", "--explain", "AAPL"])
        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "playbook" in result.output.lower() or "Full playbook" in result.output
