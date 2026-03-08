"""Weekly CFTC Commitment of Traders (COT) report collection.

Downloads the latest COT report from CFTC's website (free, no API key).
Reports are released every Friday at ~3:30pm ET for the prior Tuesday's data.

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/collect/cot.py [--history]

Options:
    --history   Download full historical data (2010–present) on first run
"""

from __future__ import annotations

import io
import sys
import zipfile
from datetime import date

import pandas as pd
import requests

sys.path.insert(0, "scripts")
from lib.db import max_date, upsert

# CFTC provides annual zip files with the legacy COT report
CFTC_ANNUAL_URL = "https://www.cftc.gov/files/dea/history/deahistfo{year}.zip"
CFTC_CURRENT_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"

# Forex-relevant contracts to track (must match CFTC "Market and Exchange Names" exactly)
FOREX_CONTRACTS = {
    "EURO FX - CHICAGO MERCANTILE EXCHANGE":            "EUR",
    "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE":      "GBP",
    "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE":       "JPY",
    "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE":        "CHF",
    "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE":    "CAD",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE":  "AUD",
    "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE":          "NZD",
    # Equity index futures
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE":     "ES",
    "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE":        "NQ",
    # Commodities
    "GOLD - COMMODITY EXCHANGE INC.":                   "GC",
    "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE": "CL",
}

COT_COLS = {
    "Market and Exchange Names":          "contract_name",
    "As of Date in Form YYMMDD":          "report_date_raw",
    "Open Interest (All)":                "open_interest",
    "Commercial Positions-Long (All)":    "commercials_long",
    "Commercial Positions-Short (All)":   "commercials_short",
    "Noncommercial Positions-Long (All)": "large_speculators_long",
    "Noncommercial Positions-Short (All)":"large_speculators_short",
    "Nonreportable Positions-Long (All)": "small_speculators_long",
    "Nonreportable Positions-Short (All)":"small_speculators_short",
}


def fetch_cot_year(year: int) -> pd.DataFrame | None:
    url = CFTC_ANNUAL_URL.format(year=year)
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 404:
            url = CFTC_CURRENT_URL.format(year=year)
            resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            fname = [n for n in z.namelist() if n.endswith(".txt")][0]
            with z.open(fname) as f:
                df = pd.read_csv(f, low_memory=False)
        return df
    except Exception as exc:
        print(f"  Warning: could not fetch {year}: {exc}")
        return None


def process_cot(df: pd.DataFrame) -> list[dict]:
    available_cols = {k: v for k, v in COT_COLS.items() if k in df.columns}
    df = df[list(available_cols.keys())].rename(columns=available_cols)

    # Filter to contracts we care about
    contract_filter = list(FOREX_CONTRACTS.keys())
    df = df[df["contract_name"].str.strip().isin(contract_filter)].copy()

    rows = []
    for _, row in df.iterrows():
        contract = row["contract_name"].strip()
        commodity = FOREX_CONTRACTS.get(contract, contract[:10])
        try:
            raw_date = str(row["report_date_raw"])
            report_date = pd.to_datetime(raw_date, format="%y%m%d").date()
        except Exception:
            continue

        rows.append({
            "report_date":             str(report_date),
            "commodity":               commodity,
            "commercials_long":        int(row.get("commercials_long", 0) or 0),
            "commercials_short":       int(row.get("commercials_short", 0) or 0),
            "large_speculators_long":  int(row.get("large_speculators_long", 0) or 0),
            "large_speculators_short": int(row.get("large_speculators_short", 0) or 0),
            "small_speculators_long":  int(row.get("small_speculators_long", 0) or 0),
            "small_speculators_short": int(row.get("small_speculators_short", 0) or 0),
        })
    return rows


def main() -> None:
    history_mode = "--history" in sys.argv
    current_year = date.today().year

    if history_mode:
        years = list(range(2010, current_year + 1))
        print(f"Fetching full COT history ({years[0]}–{years[-1]})...")
    else:
        # Only fetch current year (incremental)
        last = max_date("cot_report", "report_date")
        years = [current_year - 1, current_year] if last and last[:4] == str(current_year) else [current_year]
        print(f"Fetching COT data for {years}...")

    total = 0
    for year in years:
        df = fetch_cot_year(year)
        if df is None:
            continue
        rows = process_cot(df)
        if rows:
            written = upsert("cot_report", rows)
            total += written
            print(f"  ✓ {year}: {written} rows written")
        else:
            print(f"  - {year}: no matching contracts found")

    print(f"\n✅ COT collection complete: {total} total rows")


if __name__ == "__main__":
    main()
