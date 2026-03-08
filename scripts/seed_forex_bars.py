"""Seed forex OHLCV bars using Yahoo Finance (free, 20+ year history).

Populates forex_bars for all major and minor currency pairs.
Yahoo Finance uses EURUSD=X notation which yfinance handles natively.

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/seed_forex_bars.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime

import pandas as pd
import yfinance as yf

sys.path.insert(0, "scripts")
from lib.db import max_date, upsert

# Yahoo ticker → standard pair name
FOREX_PAIRS = {
    # Majors
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "NZDUSD=X": "NZD/USD",
    # Minors / crosses
    "EURGBP=X": "EUR/GBP",
    "EURJPY=X": "EUR/JPY",
    "GBPJPY=X": "GBP/JPY",
    "EURCHF=X": "EUR/CHF",
    "AUDNZD=X": "AUD/NZD",
    "AUDJPY=X": "AUD/JPY",
    "CADJPY=X": "CAD/JPY",
    "CHFJPY=X": "CHF/JPY",
    "GBPCHF=X": "GBP/CHF",
    "NZDJPY=X": "NZD/JPY",
    "EURAUD=X": "EUR/AUD",
    "EURCAD=X": "EUR/CAD",
    "EURNZD=X": "EUR/NZD",
    "GBPAUD=X": "GBP/AUD",
    "GBPCAD=X": "GBP/CAD",
    "GBPNZD=X": "GBP/NZD",
    "AUDCAD=X": "AUD/CAD",
    "AUDCHF=X": "AUD/CHF",
    "NZDCHF=X": "NZD/CHF",
    "NZDCAD=X": "NZD/CAD",
    "CADCHF=X": "CAD/CHF",
}


def df_to_rows(df: pd.DataFrame, pair: str) -> list[dict]:
    """Convert a yfinance OHLCV DataFrame to list of row dicts."""
    rows = []
    for idx, row in df.iterrows():
        dt = idx.date() if hasattr(idx, "date") else idx
        if pd.isna(row.get("Close", float("nan"))):
            continue
        rows.append({
            "pair":     pair,
            "date":     str(dt),
            "open":     round(float(row["Open"]), 6) if not pd.isna(row.get("Open", float("nan"))) else None,
            "high":     round(float(row["High"]), 6) if not pd.isna(row.get("High", float("nan"))) else None,
            "low":      round(float(row["Low"]), 6) if not pd.isna(row.get("Low", float("nan"))) else None,
            "close":    round(float(row["Close"]), 6),
            "interval": "1d",
            "source":   "yahoo",
        })
    return rows


def main() -> None:
    start_date = "2000-01-01"
    end_date = date.today().isoformat()

    print(f"Seeding {len(FOREX_PAIRS)} forex pairs from {start_date} to {end_date}\n")

    for yahoo_ticker, pair_name in FOREX_PAIRS.items():
        # Check for existing data (incremental)
        last = max_date("forex_bars", "date", {"pair": f"eq.{pair_name}", "interval": "eq.1d"})
        fetch_start = last or start_date

        try:
            df = yf.download(
                yahoo_ticker,
                start=fetch_start,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )

            if df.empty:
                print(f"  - {pair_name}: no data returned")
                continue

            # yf.download with single ticker returns flat columns
            if hasattr(df.columns, "levels"):
                df = df.droplevel(1, axis=1)

            rows = df_to_rows(df, pair_name)
            if not rows:
                print(f"  - {pair_name}: no rows after processing")
                continue

            written = upsert("forex_bars", rows)
            print(f"  ✓ {pair_name}: {written} rows (since {fetch_start})")

        except Exception as exc:
            print(f"  ✗ {pair_name}: FAILED — {exc}")

    print("\n✅ Forex bars seeded successfully!")


if __name__ == "__main__":
    main()
