"""Tests for the Fidelity CSV parser."""

from __future__ import annotations

import pytest

from trading.importers.base import PortfolioParser
from trading.importers.fidelity import FidelityParser

FIDELITY_HEADERS = [
    "Account Number", "Account Name", "Symbol", "Description",
    "Quantity", "Last Price", "Current Value", "Cost Basis Total",
]

FIDELITY_ROWS = [
    ["Z12345678", "INDIVIDUAL", "AAPL", "APPLE INC", "100", "190.50", "19050.00", "15025.00"],
    ["Z12345678", "INDIVIDUAL", "MSFT", "MICROSOFT CORP", "50", "380.00", "19000.00", "14500.00"],
    ["Z12345678", "INDIVIDUAL", "TSLA", "TESLA INC", "25", "250.00", "6250.00", "7500.00"],
    ["Z12345678", "INDIVIDUAL", "FCASH", "FIDELITY CASH", "1000", "1.00", "1000.00", "1000.00"],
    ["Z12345678", "INDIVIDUAL", "SPAXX", "SPAXX MONEY MARKET", "500", "1.00", "500.00", "500.00"],
]

FIDELITY_OPTION_ROWS = [
    ["Z12345678", "INDIVIDUAL", "AAPL240119C190", "AAPL JAN 19 2024 190 CALL", "5", "3.50", "1750.00", "1250.00"],
]


class TestFidelityParser:
    def test_satisfies_protocol(self):
        assert isinstance(FidelityParser(), PortfolioParser)

    def test_broker_name(self):
        assert FidelityParser().broker_name == "Fidelity"

    def test_can_parse_fidelity_headers(self):
        parser = FidelityParser()
        confidence = parser.can_parse(FIDELITY_HEADERS, FIDELITY_ROWS[:2])
        assert confidence >= 0.9

    def test_cannot_parse_random_headers(self):
        parser = FidelityParser()
        confidence = parser.can_parse(["Foo", "Bar", "Baz"], [["1", "2", "3"]])
        assert confidence == 0.0

    def test_parses_stock_positions(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        symbols = [p.symbol for p in positions]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "TSLA" in symbols

    def test_skips_cash_positions(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        symbols = [p.symbol for p in positions]
        assert "FCASH" not in symbols
        assert "SPAXX" not in symbols

    def test_parses_quantity(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        aapl = next(p for p in positions if p.symbol == "AAPL")
        assert aapl.quantity == 100

    def test_computes_per_share_cost(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        aapl = next(p for p in positions if p.symbol == "AAPL")
        # Cost Basis Total is 15025, quantity 100 → per-share = 150.25
        assert aapl.cost_basis == 150.25

    def test_sets_account(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        assert positions[0].account == "Z12345678"

    def test_detects_options_from_description(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_OPTION_ROWS, FIDELITY_HEADERS)
        assert len(positions) == 1
        assert positions[0].asset_class == "options"

    def test_equity_asset_class_default(self):
        parser = FidelityParser()
        positions = parser.parse(FIDELITY_ROWS, FIDELITY_HEADERS)
        aapl = next(p for p in positions if p.symbol == "AAPL")
        assert aapl.asset_class == "equity"

    def test_skips_footer_rows(self):
        rows_with_footer = FIDELITY_ROWS + [
            ["--", "", "", "", "", "", "", ""],
            ["", "", "", "Total", "", "", "45800.00", "38525.00"],
        ]
        parser = FidelityParser()
        positions = parser.parse(rows_with_footer, FIDELITY_HEADERS)
        # Should only parse the 3 stock rows, not cash or footer
        assert len(positions) == 3

    def test_handles_comma_in_numbers(self):
        rows = [
            ["Z12345678", "INDIVIDUAL", "NVDA", "NVIDIA CORP", "1,000", "500.00", "500,000.00", "250,000.00"],
        ]
        parser = FidelityParser()
        positions = parser.parse(rows, FIDELITY_HEADERS)
        assert positions[0].quantity == 1000
        assert positions[0].cost_basis == 250.0  # 250000 / 1000
