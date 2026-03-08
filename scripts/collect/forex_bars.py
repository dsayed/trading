"""Daily forex bar collection — fetches recent bars for all tracked pairs.

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/collect/forex_bars.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, "scripts")

# Reuse seed_forex_bars logic — it's already incremental
from seed_forex_bars import FOREX_PAIRS, df_to_rows
from lib.db import max_date, upsert

import yfinance as yf
from datetime import date, timedelta


def main() -> None:
    end_date = date.today().isoformat()
    print(f"Collecting forex bars for {len(FOREX_PAIRS)} pairs up to {end_date}")

    total = 0
    for yahoo_ticker, pair_name in FOREX_PAIRS.items():
        last = max_date("forex_bars", "date", {"pair": f"eq.{pair_name}", "interval": "eq.1d"})
        start_date = last or (date.today() - timedelta(days=7)).isoformat()

        try:
            df = yf.download(yahoo_ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
            if df.empty:
                continue
            if hasattr(df.columns, "levels"):
                df = df.droplevel(1, axis=1)
            rows = df_to_rows(df, pair_name)
            if rows:
                written = upsert("forex_bars", rows)
                total += written
        except Exception as exc:
            print(f"  ✗ {pair_name}: {exc}")

    print(f"✅ Collected {total} forex bar rows")


if __name__ == "__main__":
    main()
