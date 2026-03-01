"""Financial Modeling Prep (FMP) data provider plugin.

Implements DataProvider and DiscoveryProvider protocols.
Uses the /stable/ API namespace (v3 endpoints deprecated Aug 2025).
Requires FMP_API_KEY environment variable or passed directly.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import pandas as pd
import requests

from trading.core.models import Instrument
from trading.plugins.data._universes import (
    DOW30_CONSTITUENTS,
    GICS_SECTORS,
    NASDAQ100_CONSTITUENTS,
    SMALLCAP100_CONSTITUENTS,
    SP500_CONSTITUENTS,
)
from trading.plugins.data.base import log_api_call

logger = logging.getLogger(__name__)

FOREX_MAJORS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD",
]

BASE_URL = "https://financialmodelingprep.com"


class FMPProvider:
    """Fetches market data from Financial Modeling Prep.

    Implements DataProvider and DiscoveryProvider protocols.
    Uses hardcoded constituent lists for S&P 500 / NASDAQ 100 discovery
    (FMP free tier no longer exposes constituent or movers endpoints).
    """

    def __init__(
        self, api_key: str | None = None, calls_per_minute: int = 300
    ) -> None:
        key = api_key or os.environ.get("FMP_API_KEY", "")
        if not key:
            raise ValueError(
                "FMP API key required. Set FMP_API_KEY env var "
                "or pass api_key to FMPProvider."
            )
        self._api_key = key
        self._session = requests.Session()
        self._calls_per_minute = calls_per_minute
        self._call_times: list[float] = []

    def _throttle(self) -> None:
        """Sleep if necessary to stay within the rate limit."""
        now = time.monotonic()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self._calls_per_minute:
            sleep_for = 60 - (now - self._call_times[0]) + 0.1
            if sleep_for > 0:
                logger.info("Rate limit: waiting %.1fs", sleep_for)
                time.sleep(sleep_for)
        self._call_times.append(time.monotonic())

    def _get(self, path: str, params: dict | None = None) -> list | dict:
        """Make an authenticated GET request to FMP API."""
        self._throttle()
        url = f"{BASE_URL}{path}"
        all_params = {"apikey": self._api_key}
        if params:
            all_params.update(params)
        t0 = time.monotonic()
        try:
            resp = self._session.get(url, params=all_params, timeout=30)
            resp.raise_for_status()
            elapsed = (time.monotonic() - t0) * 1000
            log_api_call("fmp", "GET", path, elapsed)
            return resp.json()
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            log_api_call("fmp", "GET", path, elapsed, "error", str(exc))
            raise

    @property
    def name(self) -> str:
        return "fmp"

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars via FMP stable endpoint."""
        try:
            data = self._get(
                "/stable/historical-price-eod/full",
                {
                    "symbol": instrument.symbol,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                },
            )
        except Exception:
            logger.warning(
                "Failed to fetch bars for %s", instrument.symbol, exc_info=True
            )
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # Stable endpoint returns a flat list of bar objects
        bars_list = data if isinstance(data, list) else []
        if not bars_list:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        rows = []
        for bar in bars_list:
            rows.append({
                "timestamp": pd.Timestamp(bar["date"]),
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": int(bar.get("volume", 0)),
            })

        df = pd.DataFrame(rows)
        df = df.set_index("timestamp").sort_index()
        return df

    # ── DiscoveryProvider ─────────────────────────────────────────────

    def list_universe(self, universe_name: str) -> list[str]:
        """Return symbols for a named universe.

        Supported: 'sp500', 'nasdaq100', 'forex_majors'.
        Uses hardcoded constituent lists (FMP free tier deprecated
        constituent API endpoints in Aug 2025).
        """
        name = universe_name.lower()

        if name == "forex_majors":
            return list(FOREX_MAJORS)

        universe_map: dict[str, list[str]] = {
            "sp500": SP500_CONSTITUENTS,
            "nasdaq100": NASDAQ100_CONSTITUENTS,
            "dow30": DOW30_CONSTITUENTS,
            "smallcap100": SMALLCAP100_CONSTITUENTS,
        }

        if name in universe_map:
            return list(universe_map[name])

        if name in GICS_SECTORS:
            return list(GICS_SECTORS[name])

        logger.warning("Unknown universe: %s", universe_name)
        return []

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]:
        """Return empty list — FMP free tier no longer supports movers."""
        logger.warning(
            "FMP movers endpoint not available on free tier. "
            "Use polygon as discovery provider for dynamic movers."
        )
        return []
