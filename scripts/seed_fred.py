"""Seed FRED macro series — full history for all configured series.

Requires FRED_API_KEY (free at https://fred.stlouisfed.org/docs/api/api_key.html).

Populates:
  - macro_series_meta: series metadata
  - macro_series: all historical observations

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... FRED_API_KEY=... uv run python scripts/seed_fred.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, "scripts")
from lib.db import max_date, upsert

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
if not FRED_API_KEY or FRED_API_KEY.startswith("placeholder"):
    print("ERROR: FRED_API_KEY is not set.")
    print("Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
    sys.exit(1)

FRED_BASE = "https://api.stlouisfed.org/fred"

# All series to collect, grouped by category
SERIES = {
    "volatility": {
        "VIXCLS":        "CBOE Volatility Index (VIX)",
        "BAMLH0A0HYM2":  "ICE BofA US High Yield Option-Adjusted Spread",
    },
    "rates": {
        "DFF":   "Federal Funds Effective Rate",
        "DGS2":  "2-Year Treasury Constant Maturity Rate",
        "DGS10": "10-Year Treasury Constant Maturity Rate",
        "DGS30": "30-Year Treasury Constant Maturity Rate",
        "T10Y2Y": "10-Year minus 2-Year Treasury Spread",
        "T10Y3M": "10-Year minus 3-Month Treasury Spread",
    },
    "inflation": {
        "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
        "PCEPI":    "Personal Consumption Expenditures Price Index",
        "T5YIE":    "5-Year Breakeven Inflation Rate",
        "T10YIE":   "10-Year Breakeven Inflation Rate",
    },
    "labor": {
        "UNRATE":  "Unemployment Rate",
        "ICSA":    "Initial Claims (Weekly Jobless Claims)",
        "JTSJOL":  "Job Openings: Total Nonfarm",
        "CIVPART": "Labor Force Participation Rate",
    },
    "growth": {
        "A191RL1Q225SBEA": "Real Gross Domestic Product (Quarterly, % Change)",
        "RSXFS":           "Advance Retail Sales: Retail Trade",
        "INDPRO":          "Industrial Production: Total Index",
        "NAPM":            "ISM Manufacturing: PMI Composite Index",
    },
    "dollar": {
        "DTWEXBGS":  "Trade Weighted US Dollar Index: Broad, Goods and Services",
    },
    "credit": {
        "BAMLC0A0CM": "ICE BofA US Corporate Master Option-Adjusted Spread",
    },
    "money_supply": {
        "M2SL": "M2 Money Stock",
    },
    "sentiment": {
        "UMCSENT": "University of Michigan: Consumer Sentiment",
    },
}


def fetch_series_info(series_id: str) -> dict:
    resp = requests.get(
        f"{FRED_BASE}/series",
        params={"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["seriess"][0]


def fetch_observations(series_id: str, observation_start: str = "1900-01-01") -> list[dict]:
    resp = requests.get(
        f"{FRED_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": observation_start,
            "sort_order": "asc",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["observations"]


def main() -> None:
    all_series = {sid: name for cat in SERIES.values() for sid, name in cat.items()}
    print(f"Seeding {len(all_series)} FRED series...\n")

    for category, series_dict in SERIES.items():
        print(f"[{category.upper()}]")
        for series_id, series_name in series_dict.items():
            # Check what we already have (for incremental runs)
            last = max_date("macro_series", "date", {"series_id": f"eq.{series_id}"})
            obs_start = last or "1900-01-01"

            try:
                # Fetch series metadata
                info = fetch_series_info(series_id)
                meta_row = {
                    "series_id":   series_id,
                    "name":        info.get("title", series_name),
                    "description": info.get("notes", ""),
                    "frequency":   info.get("frequency_short", ""),
                    "units":       info.get("units_short", ""),
                    "category":    category,
                    "last_synced": datetime.utcnow().isoformat(),
                }
                upsert("macro_series_meta", [meta_row])

                # Fetch observations
                observations = fetch_observations(series_id, obs_start)
                # Filter out "." (missing) values
                rows = [
                    {
                        "series_id": series_id,
                        "date":      obs["date"],
                        "value":     float(obs["value"]) if obs["value"] != "." else None,
                    }
                    for obs in observations
                ]

                if rows:
                    written = upsert("macro_series", rows)
                    print(f"  ✓ {series_id}: {written} observations (since {obs_start})")
                else:
                    print(f"  - {series_id}: no new data")

            except Exception as exc:
                print(f"  ✗ {series_id}: FAILED — {exc}")

            time.sleep(0.1)  # be polite to FRED API

    print("\n✅ FRED macro series seeded successfully!")


if __name__ == "__main__":
    main()
