"""Shared Supabase REST client for seeding and collection scripts.

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from environment.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment.\n"
        "Copy .env.example to .env and fill in your values."
    )

_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


def upsert(table: str, rows: list[dict[str, Any]], batch_size: int = 500) -> int:
    """Upsert rows into a Supabase table in batches. Returns total rows written."""
    if not rows:
        return 0
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{SUPABASE_URL}/rest/v1/{table}",
                    headers=_HEADERS,
                    json=batch,
                    timeout=30,
                )
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        total += len(batch)
    return total


def select(
    table: str,
    filters: dict[str, str] | None = None,
    columns: str = "*",
    limit: int = 10_000,
) -> list[dict[str, Any]]:
    """Select rows from a Supabase table. Returns list of dicts."""
    params: dict[str, Any] = {"select": columns, "limit": limit}
    if filters:
        params.update(filters)
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**_HEADERS, "Prefer": "count=none"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def max_date(table: str, date_col: str, filters: dict[str, str] | None = None) -> str | None:
    """Return the most recent date in a table column (for incremental updates)."""
    params: dict[str, Any] = {
        "select": date_col,
        "order": f"{date_col}.desc",
        "limit": 1,
    }
    if filters:
        params.update(filters)
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**_HEADERS, "Prefer": "count=none"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0][date_col] if rows else None
