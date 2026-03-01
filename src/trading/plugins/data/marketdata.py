"""MarketData.app data provider plugin.

Implements DataProvider and OptionsDataProvider protocols.
MarketData.app has best-in-class options data with full greeks ($12/mo).
Requires MARKETDATA_API_KEY environment variable or passed directly.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import pandas as pd
import requests

from trading.core.models import Instrument, OptionChain, OptionContract

logger = logging.getLogger(__name__)

BASE_URL = "https://api.marketdata.app"


class MarketDataProvider:
    """Fetches market data from MarketData.app.

    Implements DataProvider and OptionsDataProvider protocols.
    MarketData.app excels at options data — full greeks (delta, gamma, theta,
    vega) and implied volatility on every contract.
    """

    def __init__(
        self, api_key: str | None = None, calls_per_minute: int = 100
    ) -> None:
        key = api_key or os.environ.get("MARKETDATA_API_KEY", "")
        if not key:
            raise ValueError(
                "MarketData API key required. Set MARKETDATA_API_KEY env var "
                "or pass api_key to MarketDataProvider."
            )
        self._api_key = key
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {key}"
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

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to MarketData.app API."""
        self._throttle()
        url = f"{BASE_URL}{path}"
        resp = self._session.get(url, params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @property
    def name(self) -> str:
        return "marketdata"

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars via MarketData candles endpoint."""
        try:
            data = self._get(
                f"/v1/stocks/candles/daily/{instrument.symbol}",
                {"from": start.isoformat(), "to": end.isoformat()},
            )
        except Exception:
            logger.warning(
                "Failed to fetch bars for %s", instrument.symbol, exc_info=True
            )
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if data.get("s") != "ok":
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        rows = []
        timestamps = data.get("t", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])
        volumes = data.get("v", [])

        for i in range(len(timestamps)):
            rows.append({
                "timestamp": pd.Timestamp(timestamps[i], unit="s"),
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": int(volumes[i]) if i < len(volumes) else 0,
            })

        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(rows)
        df = df.set_index("timestamp").sort_index()
        return df

    # ── OptionsDataProvider ───────────────────────────────────────────

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        """Fetch option chains with full greeks from MarketData.app."""
        params: dict = {}
        if expiration:
            params["expiration"] = expiration.isoformat()

        try:
            data = self._get(
                f"/v1/options/chain/{instrument.symbol}", params
            )
        except Exception:
            logger.warning(
                "Failed to fetch option chain for %s",
                instrument.symbol, exc_info=True,
            )
            return []

        if data.get("s") != "ok":
            return []

        # MarketData returns arrays of contract fields
        option_symbols = data.get("optionSymbol", [])
        strikes = data.get("strike", [])
        expirations = data.get("expiration", [])
        sides = data.get("side", [])
        bids = data.get("bid", [])
        asks = data.get("ask", [])
        lasts = data.get("last", [])
        volumes = data.get("volume", [])
        open_interests = data.get("openInterest", [])
        ivs = data.get("iv", [])
        itms = data.get("inTheMoney", [])

        # Group by expiration
        by_expiration: dict[date, dict[str, list[OptionContract]]] = {}
        for i in range(len(option_symbols)):
            exp = date.fromisoformat(str(expirations[i])[:10]) if i < len(expirations) else date.today()
            if exp not in by_expiration:
                by_expiration[exp] = {"calls": [], "puts": []}

            opt = OptionContract(
                contract_symbol=option_symbols[i] if i < len(option_symbols) else "",
                strike=float(strikes[i]) if i < len(strikes) else 0.0,
                expiration=exp,
                option_type="call" if (sides[i] if i < len(sides) else "call") == "call" else "put",
                bid=float(bids[i]) if i < len(bids) else 0.0,
                ask=float(asks[i]) if i < len(asks) else 0.0,
                last_price=float(lasts[i]) if i < len(lasts) else 0.0,
                volume=int(volumes[i] or 0) if i < len(volumes) else 0,
                open_interest=int(open_interests[i] or 0) if i < len(open_interests) else 0,
                implied_volatility=float(ivs[i] or 0) if i < len(ivs) else 0.0,
                in_the_money=bool(itms[i]) if i < len(itms) else False,
            )
            side = "calls" if opt.option_type == "call" else "puts"
            by_expiration[exp][side].append(opt)

        chains = []
        for exp in sorted(by_expiration.keys()):
            chains.append(
                OptionChain(
                    instrument=instrument,
                    expiration=exp,
                    calls=by_expiration[exp]["calls"],
                    puts=by_expiration[exp]["puts"],
                )
            )
        return chains

    def fetch_current_price(self, instrument: Instrument) -> float:
        """Fetch latest price via MarketData quotes endpoint."""
        try:
            data = self._get(f"/v1/stocks/quotes/{instrument.symbol}")
            if data.get("s") == "ok" and data.get("last"):
                return float(data["last"][0])
            return 0.0
        except Exception:
            logger.warning(
                "Failed to fetch current price for %s",
                instrument.symbol, exc_info=True,
            )
            return 0.0
