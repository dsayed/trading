"""Financial Modeling Prep (FMP) data provider plugin.

Implements DataProvider and DiscoveryProvider protocols.
FMP has excellent screener/discovery APIs ($22/mo) and broad stock data.
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

logger = logging.getLogger(__name__)

FOREX_MAJORS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD",
]

BASE_URL = "https://financialmodelingprep.com"


class FMPProvider:
    """Fetches market data from Financial Modeling Prep.

    Implements DataProvider and DiscoveryProvider protocols.
    FMP excels at discovery/screening with accurate S&P 500 and NASDAQ 100
    constituent lists and market movers.
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
        resp = self._session.get(url, params=all_params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @property
    def name(self) -> str:
        return "fmp"

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars via FMP historical price endpoint."""
        try:
            data = self._get(
                f"/api/v3/historical-price-full/{instrument.symbol}",
                {"from": start.isoformat(), "to": end.isoformat()},
            )
        except Exception:
            logger.warning(
                "Failed to fetch bars for %s", instrument.symbol, exc_info=True
            )
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        historical = data.get("historical", []) if isinstance(data, dict) else []
        if not historical:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        rows = []
        for bar in historical:
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
        FMP has dedicated endpoints for index constituents.
        """
        name = universe_name.lower()

        if name == "forex_majors":
            return list(FOREX_MAJORS)

        endpoint_map = {
            "sp500": "/api/v3/sp500_constituent",
            "nasdaq100": "/api/v3/nasdaq_constituent",
        }

        if name not in endpoint_map:
            logger.warning("Unknown universe: %s", universe_name)
            return []

        try:
            data = self._get(endpoint_map[name])
            if isinstance(data, list):
                return [item["symbol"] for item in data if "symbol" in item]
            return []
        except Exception:
            logger.warning(
                "Failed to list universe %s", universe_name, exc_info=True
            )
            return []

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]:
        """Get top movers (gainers/losers) via FMP market movers endpoint."""
        endpoint_map = {
            "gainers": "/api/v3/stock_market/gainers",
            "losers": "/api/v3/stock_market/losers",
        }

        endpoint = endpoint_map.get(direction, endpoint_map["gainers"])

        try:
            data = self._get(endpoint)
        except Exception:
            logger.warning(
                "Failed to fetch movers (%s)", direction, exc_info=True
            )
            return []

        if not isinstance(data, list):
            return []

        results = []
        for item in data[:limit]:
            results.append({
                "symbol": item.get("symbol", ""),
                "change_pct": round(float(item.get("changesPercentage", 0)), 2),
                "volume": int(item.get("volume", 0) or 0),
                "price": round(float(item.get("price", 0)), 2),
            })

        return results
