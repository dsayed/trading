"""Weekly FRED macro series update — fetches new observations since last sync.

Run:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... FRED_API_KEY=... uv run python scripts/collect/fred.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, "scripts")

# Reuse seed_fred logic — it's already incremental
from seed_fred import SERIES, fetch_observations, fetch_series_info
from lib.db import max_date, upsert
from datetime import datetime
import time


def main() -> None:
    all_series = {sid: name for cat in SERIES.values() for sid, name in cat.items()}
    print(f"Updating {len(all_series)} FRED series (incremental)...\n")

    for category, series_dict in SERIES.items():
        for series_id in series_dict:
            last = max_date("macro_series", "date", {"series_id": f"eq.{series_id}"})
            obs_start = last or "2000-01-01"

            try:
                observations = fetch_observations(series_id, obs_start)
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
                    print(f"  ✓ {series_id}: +{written} new observations")
                    # Update last_synced
                    upsert("macro_series_meta", [{"series_id": series_id, "last_synced": datetime.utcnow().isoformat()}])
                else:
                    print(f"  - {series_id}: up to date")
            except Exception as exc:
                print(f"  ✗ {series_id}: {exc}")
            time.sleep(0.1)

    print("\n✅ FRED update complete")


if __name__ == "__main__":
    main()
