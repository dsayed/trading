"""Tests for the parser registry and auto-detection."""

from __future__ import annotations

import pytest

from trading.importers.registry import detect_and_parse


FIDELITY_CSV = """Account Number,Account Name,Symbol,Description,Quantity,Last Price,Current Value,Cost Basis Total
Z12345678,INDIVIDUAL,AAPL,APPLE INC,100,190.50,19050.00,15025.00
Z12345678,INDIVIDUAL,MSFT,MICROSOFT CORP,50,380.00,19000.00,14500.00
Z12345678,INDIVIDUAL,FCASH,FIDELITY CASH,1000,1.00,1000.00,1000.00
"""

GENERIC_CSV = """Symbol,Quantity,Cost Basis
AAPL,100,150.25
GOOG,10,140.50
"""

EMPTY_CSV = ""

HEADERS_ONLY_CSV = """Symbol,Quantity,Cost Basis
"""

UNRECOGNIZED_CSV = """Date,Weather,Temperature
2024-01-01,Sunny,72
2024-01-02,Cloudy,65
"""


class TestDetectAndParse:
    def test_detects_fidelity(self):
        broker, positions = detect_and_parse(FIDELITY_CSV)
        assert broker == "Fidelity"
        assert len(positions) == 2  # Skips FCASH
        assert positions[0].symbol == "AAPL"

    def test_detects_generic(self):
        broker, positions = detect_and_parse(GENERIC_CSV)
        assert broker == "Generic CSV"
        assert len(positions) == 2

    def test_fidelity_wins_over_generic(self):
        # Fidelity CSV also has Symbol/Quantity, but should be detected as Fidelity
        broker, _ = detect_and_parse(FIDELITY_CSV)
        assert broker == "Fidelity"

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="empty"):
            detect_and_parse(EMPTY_CSV)

    def test_headers_only_raises(self):
        with pytest.raises(ValueError, match="no data"):
            detect_and_parse(HEADERS_ONLY_CSV)

    def test_unrecognized_format_raises(self):
        with pytest.raises(ValueError, match="Could not identify"):
            detect_and_parse(UNRECOGNIZED_CSV)
