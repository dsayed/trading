"""Seed equity OHLCV bars using Yahoo Finance — 20+ year history.

Reads the symbol universe from Supabase (index_constituents + instruments),
then bulk-downloads daily bars for all symbols via yfinance.

Run seed_sp500_constituents.py FIRST to populate the symbol universe.

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/seed_equity_bars.py [--batch N]

Options:
    --batch N   Process N symbols at a time (default: 100). Reduce if hitting rate limits.
"""

from __future__ import annotations

import sys
import time
from datetime import date

import pandas as pd
import yfinance as yf

sys.path.insert(0, "scripts")
from lib.db import max_date, select, upsert

START_DATE = "2000-01-01"
BATCH_SIZE = 100  # symbols per yfinance download call


def get_universe() -> list[str]:
    """Get all unique symbols from index_constituents + instruments."""
    # Symbols that were ever in the S&P 500
    constituents = select("index_constituents", {"index_name": "eq.SP500"}, columns="symbol")
    sp500_symbols = list({r["symbol"] for r in constituents})

    # Extra ETFs and instruments
    instruments = select("instruments", {"asset_class": "eq.etf"}, columns="symbol")
    etf_symbols = [r["symbol"] for r in instruments]

    all_symbols = sorted(set(sp500_symbols + etf_symbols))
    print(f"Universe: {len(sp500_symbols)} S&P500 historical + {len(etf_symbols)} ETFs = {len(all_symbols)} unique")
    return all_symbols


def download_batch(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """Download a batch of symbols and return dict of symbol → DataFrame."""
    try:
        raw = yf.download(
            symbols,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as exc:
        print(f"    Download error: {exc}")
        return {}

    if raw.empty:
        return {}

    result = {}
    if len(symbols) == 1:
        sym = symbols[0]
        if not raw.empty:
            result[sym] = raw
    else:
        for sym in symbols:
            try:
                df = raw[sym].dropna(how="all")
                if not df.empty:
                    result[sym] = df
            except (KeyError, TypeError):
                pass
    return result


def df_to_rows(df: pd.DataFrame, symbol: str) -> list[dict]:
    """Convert OHLCV DataFrame to list of row dicts."""
    rows = []
    for idx, row in df.iterrows():
        dt = idx.date() if hasattr(idx, "date") else idx
        close = row.get("Close", float("nan"))
        if pd.isna(close):
            continue
        rows.append({
            "symbol":   symbol,
            "date":     str(dt),
            "open":     round(float(row["Open"]), 4) if not pd.isna(row.get("Open", float("nan"))) else None,
            "high":     round(float(row["High"]), 4) if not pd.isna(row.get("High", float("nan"))) else None,
            "low":      round(float(row["Low"]), 4) if not pd.isna(row.get("Low", float("nan"))) else None,
            "close":    round(float(close), 4),
            "volume":   int(row["Volume"]) if not pd.isna(row.get("Volume", float("nan"))) else None,
            "interval": "1d",
            "source":   "yahoo",
        })
    return rows


def main() -> None:
    end_date = date.today().isoformat()
    symbols = get_universe()

    print(f"\nDownloading daily bars from {START_DATE} to {end_date}")
    print(f"Processing {len(symbols)} symbols in batches of {BATCH_SIZE}\n")

    total_rows = 0
    failed = []

    for batch_start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"Batch {batch_num}/{total_batches}: {batch[0]}...{batch[-1]}")

        dfs = download_batch(batch, START_DATE, end_date)

        all_rows = []
        for sym, df in dfs.items():
            rows = df_to_rows(df, sym)
            all_rows.extend(rows)

        if all_rows:
            written = upsert("equity_bars", all_rows)
            total_rows += written
            print(f"  → {len(dfs)} symbols downloaded, {written} rows written")
        else:
            print(f"  → no data returned for this batch")
            failed.extend([s for s in batch if s not in dfs])

        time.sleep(1)  # rate limit courtesy

    print(f"\n✅ Equity bars seeded: {total_rows:,} total rows")
    if failed:
        print(f"⚠️  {len(failed)} symbols failed: {', '.join(failed[:20])}")


if __name__ == "__main__":
    main()
