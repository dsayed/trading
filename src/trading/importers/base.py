"""Base types and protocol for portfolio CSV parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ImportedPosition:
    """A position parsed from a CSV file."""

    symbol: str
    quantity: int
    cost_basis: float
    purchase_date: str  # ISO format
    asset_class: str
    account: str | None = None
    description: str | None = None


@runtime_checkable
class PortfolioParser(Protocol):
    @property
    def broker_name(self) -> str: ...

    def can_parse(self, headers: list[str], sample_rows: list[list[str]]) -> float: ...

    def parse(self, rows: list[list[str]], headers: list[str]) -> list[ImportedPosition]: ...
