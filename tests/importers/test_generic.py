"""Tests for the generic CSV parser."""

from __future__ import annotations

import pytest

from trading.importers.base import PortfolioParser
from trading.importers.generic import GenericParser

GENERIC_HEADERS = ["Symbol", "Quantity", "Cost Basis"]
GENERIC_ROWS = [
    ["AAPL", "100", "150.25"],
    ["MSFT", "50", "290.00"],
    ["GOOG", "10", "140.50"],
]


class TestGenericParser:
    def test_satisfies_protocol(self):
        assert isinstance(GenericParser(), PortfolioParser)

    def test_broker_name(self):
        assert GenericParser().broker_name == "Generic CSV"

    def test_can_parse_standard_headers(self):
        parser = GenericParser()
        confidence = parser.can_parse(GENERIC_HEADERS, GENERIC_ROWS[:2])
        assert 0.1 < confidence < 0.5  # Lower confidence than broker-specific

    def test_cannot_parse_unrelated_headers(self):
        parser = GenericParser()
        confidence = parser.can_parse(["Date", "Weather", "Temp"], [["2024-01-01", "Sunny", "72"]])
        assert confidence < 0.1

    def test_parses_positions(self):
        parser = GenericParser()
        positions = parser.parse(GENERIC_ROWS, GENERIC_HEADERS)
        assert len(positions) == 3
        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == 100
        assert positions[0].cost_basis == 150.25

    def test_flexible_column_names(self):
        # Uses "Ticker" and "Shares" instead of "Symbol" and "Quantity"
        headers = ["Ticker", "Shares", "Avg Cost"]
        rows = [["AAPL", "100", "150.25"]]
        parser = GenericParser()
        confidence = parser.can_parse(headers, rows)
        assert confidence > 0.1

    def test_defaults_to_equity(self):
        parser = GenericParser()
        positions = parser.parse(GENERIC_ROWS, GENERIC_HEADERS)
        assert all(p.asset_class == "equity" for p in positions)

    def test_skips_zero_quantity(self):
        rows = [["AAPL", "0", "150.25"]]
        parser = GenericParser()
        positions = parser.parse(rows, GENERIC_HEADERS)
        assert positions == []

    def test_handles_dollar_signs(self):
        rows = [["AAPL", "100", "$150.25"]]
        parser = GenericParser()
        positions = parser.parse(rows, GENERIC_HEADERS)
        assert positions[0].cost_basis == 150.25
