"""Parser registry with auto-detection of CSV broker format."""

from __future__ import annotations

import csv
import io

from trading.importers.base import ImportedPosition
from trading.importers.fidelity import FidelityParser
from trading.importers.generic import GenericParser

PARSERS = [FidelityParser(), GenericParser()]


def detect_and_parse(content: str) -> tuple[str, list[ImportedPosition]]:
    """Auto-detect broker and parse CSV. Returns (broker_name, positions).

    Tries all registered parsers and picks the highest-confidence match.
    Raises ValueError if no parser can handle the CSV.
    """
    reader = csv.reader(io.StringIO(content))
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("CSV file is empty")

    rows = list(reader)
    if not rows:
        raise ValueError("CSV file has headers but no data rows")

    sample = rows[:5]
    best = max(PARSERS, key=lambda p: p.can_parse(headers, sample))
    confidence = best.can_parse(headers, sample)

    if confidence < 0.1:
        raise ValueError(
            "Could not identify CSV format. Expected columns like "
            "Symbol, Quantity, Cost Basis."
        )

    positions = best.parse(rows, headers)
    return best.broker_name, positions
