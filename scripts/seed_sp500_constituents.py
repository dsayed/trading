"""Seed S&P 500 historical constituents from fja05680/sp500 GitHub repo.

Populates:
  - index_constituents: every symbol's date_added / date_removed since 1996
  - instruments: unique ticker records

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/seed_sp500_constituents.py
"""

from __future__ import annotations

import io
import sys

import pandas as pd
import requests

sys.path.insert(0, "scripts")
from lib.db import upsert

CSV_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "sp500_ticker_start_end.csv"
)

# Additional ETFs and index proxies to always include
EXTRA_SYMBOLS = [
    # Broad market ETFs
    "SPY", "QQQ", "IWM", "DIA", "VTI",
    # Sector ETFs
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE", "XLU",
    # Fixed income
    "TLT", "IEF", "SHY", "HYG", "LQD",
    # Volatility
    "VXX", "UVXY", "SVXY",
    # Commodities
    "GLD", "SLV", "USO", "UNG", "DBC",
    # International
    "EFA", "EEM", "VEA", "VWO",
    # Dollar
    "UUP",
]


def main() -> None:
    print("Fetching S&P 500 historical constituent data...")
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text))
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date.astype(str)
    df["end_date"] = df["end_date"].where(df["end_date"].notna(), None)
    df.loc[df["end_date"].notna(), "end_date"] = (
        pd.to_datetime(df.loc[df["end_date"].notna(), "end_date"])
        .dt.date.astype(str)
    )

    print(f"  {len(df)} constituent records for {df['ticker'].nunique()} unique symbols")

    # Build index_constituents rows
    constituent_rows = [
        {
            "index_name": "SP500",
            "symbol": row["ticker"],
            "date_added": row["start_date"],
            "date_removed": row["end_date"] if pd.notna(row["end_date"]) else None,
        }
        for _, row in df.iterrows()
    ]

    print(f"Writing {len(constituent_rows)} rows to index_constituents...")
    written = upsert("index_constituents", constituent_rows)
    print(f"  ✓ {written} rows written")

    # Build instruments rows for all unique S&P500 symbols
    sp500_symbols = df["ticker"].unique().tolist()
    all_symbols = list(set(sp500_symbols + EXTRA_SYMBOLS))
    instrument_rows = [
        {"symbol": sym, "asset_class": "equity"}
        for sym in sorted(all_symbols)
    ]
    # Mark ETFs
    for row in instrument_rows:
        if row["symbol"] in EXTRA_SYMBOLS:
            row["asset_class"] = "etf"

    print(f"Writing {len(instrument_rows)} rows to instruments...")
    written = upsert("instruments", instrument_rows)
    print(f"  ✓ {written} rows written")

    # Also seed current S&P500 members from sp500.csv
    current_url = (
        "https://raw.githubusercontent.com/fja05680/sp500/master/sp500.csv"
    )
    try:
        resp2 = requests.get(current_url, timeout=15)
        resp2.raise_for_status()
        current_df = pd.read_csv(io.StringIO(resp2.text))
        # Update asset_class for current members
        ticker_col = "Symbol" if "Symbol" in current_df.columns else current_df.columns[0]
        current_symbols = current_df[ticker_col].tolist()
        print(f"  Current S&P 500 has {len(current_symbols)} members")
    except Exception as exc:
        print(f"  Warning: could not fetch current sp500.csv: {exc}")

    print("\n✅ S&P 500 constituents seeded successfully!")
    print(f"   {df['ticker'].nunique()} unique historical S&P 500 symbols")
    print(f"   {len(EXTRA_SYMBOLS)} extra ETF/index symbols")


if __name__ == "__main__":
    main()
