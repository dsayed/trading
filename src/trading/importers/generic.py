"""Generic CSV portfolio parser — fallback for unrecognized formats.

Matches any CSV that has columns resembling symbol + quantity + cost.
Lower confidence (0.3) so broker-specific parsers always win.
"""

from __future__ import annotations

import logging
from datetime import date

from trading.importers.base import ImportedPosition

logger = logging.getLogger(__name__)

# Flexible column name matching
SYMBOL_NAMES = {"symbol", "ticker", "stock", "name", "security"}
QTY_NAMES = {"quantity", "qty", "shares", "amount", "units"}
COST_NAMES = {"cost basis", "cost_basis", "cost basis total", "avg cost", "average cost", "price", "cost"}


class GenericParser:
    """Fallback CSV parser for unknown brokers."""

    @property
    def broker_name(self) -> str:
        return "Generic CSV"

    def can_parse(self, headers: list[str], sample_rows: list[list[str]]) -> float:
        normalized = {h.strip().lower() for h in headers}
        has_symbol = bool(normalized & SYMBOL_NAMES)
        has_qty = bool(normalized & QTY_NAMES)
        has_cost = bool(normalized & COST_NAMES)

        if has_symbol and has_qty and has_cost:
            return 0.3
        if has_symbol and has_qty:
            return 0.15
        return 0.0

    def parse(self, rows: list[list[str]], headers: list[str]) -> list[ImportedPosition]:
        normalized = [h.strip().lower() for h in headers]

        symbol_idx = _find_col(normalized, SYMBOL_NAMES)
        qty_idx = _find_col(normalized, QTY_NAMES)
        cost_idx = _find_col(normalized, COST_NAMES)

        if symbol_idx is None or qty_idx is None:
            return []

        today = date.today().isoformat()
        results: list[ImportedPosition] = []

        for row in rows:
            if len(row) <= max(symbol_idx, qty_idx):
                continue

            symbol = row[symbol_idx].strip()
            if not symbol:
                continue

            qty_str = row[qty_idx].strip().replace(",", "")
            try:
                qty = int(float(qty_str))
            except ValueError:
                continue

            if qty == 0:
                continue

            cost_basis = 0.0
            if cost_idx is not None and cost_idx < len(row):
                cost_str = row[cost_idx].strip().replace(",", "").replace("$", "")
                try:
                    cost_basis = float(cost_str)
                except ValueError:
                    pass

            results.append(
                ImportedPosition(
                    symbol=symbol.upper(),
                    quantity=qty,
                    cost_basis=round(cost_basis, 4),
                    purchase_date=today,
                    asset_class="equity",
                )
            )

        return results


def _find_col(headers: list[str], candidates: set[str]) -> int | None:
    for idx, h in enumerate(headers):
        if h in candidates:
            return idx
    return None
