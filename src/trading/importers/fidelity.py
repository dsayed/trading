"""Fidelity brokerage CSV parser.

Handles the standard Fidelity "Positions" export format:
- Headers: Account Number, Account Name, Symbol, Description, Quantity,
           Last Price, Current Value, Cost Basis Total, ...
- Skips cash/money-market rows (FCASH, SPAXX, pending activity)
- Detects options from Description column
- Note: Standard Fidelity CSV does not include purchase dates
"""

from __future__ import annotations

import logging
import re
from datetime import date

from trading.importers.base import ImportedPosition

logger = logging.getLogger(__name__)

CASH_SYMBOLS = {"FCASH", "SPAXX", "FDRXX", "FZFXX", "CORE"}


class FidelityParser:
    """Parses Fidelity position export CSVs."""

    @property
    def broker_name(self) -> str:
        return "Fidelity"

    def can_parse(self, headers: list[str], sample_rows: list[list[str]]) -> float:
        """Return confidence 0-1 that this CSV is from Fidelity."""
        normalized = [h.strip().lower() for h in headers]
        has_account = "account number" in normalized or "account name" in normalized
        has_cost_basis = "cost basis total" in normalized
        has_symbol = "symbol" in normalized

        if has_account and has_cost_basis and has_symbol:
            return 0.9
        if has_account and has_symbol:
            return 0.6
        return 0.0

    def parse(self, rows: list[list[str]], headers: list[str]) -> list[ImportedPosition]:
        """Parse Fidelity CSV rows into ImportedPosition objects."""
        normalized = [h.strip().lower() for h in headers]

        # Build column index map
        col = {name: idx for idx, name in enumerate(normalized)}

        symbol_idx = col.get("symbol")
        desc_idx = col.get("description")
        qty_idx = col.get("quantity")
        cost_total_idx = col.get("cost basis total")
        account_idx = col.get("account number")
        if account_idx is None:
            account_idx = col.get("account name")

        if symbol_idx is None or qty_idx is None:
            return []

        results: list[ImportedPosition] = []
        today = date.today().isoformat()

        for row in rows:
            if len(row) <= max(symbol_idx, qty_idx):
                continue

            symbol = row[symbol_idx].strip()

            # Skip empty, cash, totals, and footer rows
            if not symbol or symbol.upper() in CASH_SYMBOLS:
                continue
            if symbol.startswith("--") or symbol.lower() in ("", "pending activity"):
                continue

            # Parse quantity
            qty_str = row[qty_idx].strip().replace(",", "")
            if not qty_str or qty_str == "--" or qty_str.lower() == "n/a":
                continue
            try:
                qty = int(float(qty_str))
            except ValueError:
                continue

            if qty == 0:
                continue

            # Parse cost basis
            cost_basis = 0.0
            if cost_total_idx is not None and cost_total_idx < len(row):
                cost_str = row[cost_total_idx].strip().replace(",", "").replace("$", "")
                if cost_str and cost_str not in ("--", "n/a", "N/A"):
                    try:
                        total_cost = float(cost_str)
                        cost_basis = total_cost / qty if qty != 0 else 0.0
                    except ValueError:
                        pass

            # Detect options from description
            description = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else None
            asset_class = "equity"
            if description and _looks_like_option(description):
                asset_class = "options"

            account = row[account_idx].strip() if account_idx is not None and account_idx < len(row) else None

            results.append(
                ImportedPosition(
                    symbol=symbol.upper(),
                    quantity=qty,
                    cost_basis=round(cost_basis, 4),
                    purchase_date=today,  # Fidelity doesn't export purchase dates
                    asset_class=asset_class,
                    account=account,
                    description=description,
                )
            )

        return results


def _looks_like_option(description: str) -> bool:
    """Detect option positions from Fidelity description field."""
    # "AAPL JAN 19 2024 190 CALL" or similar
    option_pattern = r"\b(CALL|PUT)\b"
    return bool(re.search(option_pattern, description.upper()))
