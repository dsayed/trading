"""Daily equity bar collection — fetches yesterday's bars for all tracked symbols.

Designed for daily cron runs after market close (8pm ET Mon–Fri).
Only fetches data since the most recent bar per symbol (incremental).

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/collect/equity_bars.py
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

sys.path.insert(0, "scripts")
from lib.db import max_date, select, upsert

BATCH_SIZE = 200


def get_tracked_symbols() -> list[str]:
    rows = select("instruments", columns="symbol")
    return sorted({r["symbol"] for r in rows})


def main() -> None:
    end_date = date.today().isoformat()
    symbols = get_tracked_symbols()
    print(f"Collecting bars for {len(symbols)} symbols up to {end_date}")

    total = 0
    for batch_start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[batch_start : batch_start + BATCH_SIZE]

        # Find the latest date across this batch (use yesterday as default)
        start_date = (date.today() - timedelta(days=5)).isoformat()

        try:
            raw = yf.download(
                batch,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                group_by="ticker",
            )
        except Exception as exc:
            print(f"  Batch error: {exc}")
            continue

        if raw.empty:
            continue

        all_rows = []
        for sym in batch:
            try:
                df = raw[sym].dropna(how="all") if len(batch) > 1 else raw.dropna(how="all")
                for idx, row in df.iterrows():
                    dt = idx.date() if hasattr(idx, "date") else idx
                    close = row.get("Close", float("nan"))
                    if pd.isna(close):
                        continue
                    all_rows.append({
                        "symbol":   sym,
                        "date":     str(dt),
                        "open":     round(float(row["Open"]), 4) if not pd.isna(row.get("Open", float("nan"))) else None,
                        "high":     round(float(row["High"]), 4) if not pd.isna(row.get("High", float("nan"))) else None,
                        "low":      round(float(row["Low"]), 4) if not pd.isna(row.get("Low", float("nan"))) else None,
                        "close":    round(float(close), 4),
                        "volume":   int(row["Volume"]) if not pd.isna(row.get("Volume", float("nan"))) else None,
                        "interval": "1d",
                        "source":   "yahoo",
                    })
            except (KeyError, TypeError):
                pass

        if all_rows:
            written = upsert("equity_bars", all_rows)
            total += written

        time.sleep(0.5)

    print(f"✅ Collected {total} equity bar rows")


if __name__ == "__main__":
    main()
