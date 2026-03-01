"""Polygon.io data provider plugin.

Implements DataProvider, OptionsDataProvider, and DiscoveryProvider protocols.
Requires a Polygon.io API key (starter plan $29/month) set via POLYGON_API_KEY
environment variable or passed directly.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import pandas as pd

from trading.core.models import Instrument, OptionChain, OptionContract
from trading.plugins.data._universes import (
    DOW30_CONSTITUENTS,
    GICS_SECTORS,
    SMALLCAP100_CONSTITUENTS,
)
from trading.plugins.data.base import log_api_call

logger = logging.getLogger(__name__)

# Hardcoded forex majors — no API needed for this small list.
FOREX_MAJORS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD",
]


class PolygonProvider:
    """Fetches market data from Polygon.io (stocks, options, forex).

    Implements DataProvider, OptionsDataProvider, and DiscoveryProvider
    protocols for the trading engine plugin system.
    """

    def __init__(
        self, api_key: str | None = None, calls_per_minute: int = 5
    ) -> None:
        from polygon import RESTClient

        key = api_key or os.environ.get("POLYGON_API_KEY", "")
        if not key:
            raise ValueError(
                "Polygon API key required. Set POLYGON_API_KEY env var "
                "or pass api_key to PolygonProvider."
            )
        self._client = RESTClient(api_key=key)
        # Rate limiting: track call timestamps to stay under the limit
        self._calls_per_minute = calls_per_minute
        self._call_times: list[float] = []

    def _throttle(self) -> None:
        """Sleep if necessary to stay within the rate limit."""
        now = time.monotonic()
        # Purge calls older than 60 seconds
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self._calls_per_minute:
            # Wait until the oldest call falls outside the 60s window
            sleep_for = 60 - (now - self._call_times[0]) + 0.1
            if sleep_for > 0:
                logger.info("Rate limit: waiting %.1fs", sleep_for)
                time.sleep(sleep_for)
        self._call_times.append(time.monotonic())

    @property
    def name(self) -> str:
        return "polygon"

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars via Polygon aggregates endpoint."""
        # Polygon uses C: prefix for forex tickers
        ticker = self._to_polygon_ticker(instrument)

        try:
            self._throttle()
            t0 = time.monotonic()
            aggs = list(
                self._client.list_aggs(
                    ticker=ticker,
                    multiplier=1,
                    timespan="day",
                    from_=start.isoformat(),
                    to=end.isoformat(),
                    limit=50000,
                )
            )
            elapsed = (time.monotonic() - t0) * 1000
            log_api_call("polygon", "SDK", f"list_aggs({ticker})", elapsed)
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            log_api_call("polygon", "SDK", f"list_aggs({ticker})", elapsed, "error", str(exc))
            logger.warning(
                "Failed to fetch bars for %s", instrument.symbol, exc_info=True
            )
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if not aggs:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        rows = []
        for a in aggs:
            rows.append({
                "timestamp": pd.Timestamp(a.timestamp, unit="ms"),
                "open": a.open,
                "high": a.high,
                "low": a.low,
                "close": a.close,
                "volume": int(a.volume or 0),
            })

        df = pd.DataFrame(rows)
        df = df.set_index("timestamp").sort_index()
        return df

    # ── OptionsDataProvider ───────────────────────────────────────────

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        """Fetch option chains via Polygon options endpoints."""
        try:
            params: dict = {
                "underlying_ticker": instrument.symbol,
                "limit": 250,
            }
            if expiration:
                params["expiration_date"] = expiration.isoformat()

            self._throttle()
            contracts = list(
                self._client.list_options_contracts(**params)
            )
        except Exception:
            logger.warning(
                "Failed to fetch option contracts for %s",
                instrument.symbol, exc_info=True,
            )
            return []

        if not contracts:
            return []

        # Group by expiration
        by_expiration: dict[date, dict[str, list[OptionContract]]] = {}
        for c in contracts:
            exp = date.fromisoformat(c.expiration_date) if isinstance(c.expiration_date, str) else c.expiration_date
            if exp not in by_expiration:
                by_expiration[exp] = {"calls": [], "puts": []}

            # Try to get snapshot for greeks/pricing
            bid, ask, last, iv, vol, oi = 0.0, 0.0, 0.0, 0.0, 0, 0
            try:
                self._throttle()
                snap = self._client.get_snapshot_option(
                    instrument.symbol, c.ticker
                )
                if snap and snap.day:
                    last = float(snap.day.close or 0)
                    vol = int(snap.day.volume or 0)
                if snap and snap.details:
                    oi = int(snap.open_interest or 0)
                if snap and snap.greeks:
                    iv = float(snap.implied_volatility or 0)
            except Exception:
                pass  # Pricing is best-effort

            opt = OptionContract(
                contract_symbol=c.ticker,
                strike=float(c.strike_price),
                expiration=exp,
                option_type=c.contract_type.lower() if c.contract_type else "call",
                bid=bid,
                ask=ask,
                last_price=last,
                volume=vol,
                open_interest=oi,
                implied_volatility=iv,
                in_the_money=False,  # Determined by caller if needed
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
        """Fetch latest price via Polygon last trade or snapshot."""
        ticker = self._to_polygon_ticker(instrument)
        try:
            self._throttle()
            trade = self._client.get_last_trade(ticker=ticker)
            return float(trade.price)
        except Exception:
            logger.warning(
                "Failed to fetch current price for %s", instrument.symbol, exc_info=True
            )
            return 0.0

    # ── DiscoveryProvider ─────────────────────────────────────────────

    def list_universe(self, universe_name: str) -> list[str]:
        """Return symbols for a named universe.

        Supported: 'sp500', 'nasdaq100', 'forex_majors'.
        Uses Polygon reference/tickers API for equity indices.
        """
        name = universe_name.lower()

        if name == "forex_majors":
            return list(FOREX_MAJORS)

        # Map universe name to Polygon market/exchange filter
        exchange_map = {
            "sp500": {"market": "stocks", "exchange": "XNYS"},
            "nasdaq100": {"market": "stocks", "exchange": "XNAS"},
        }

        if name not in exchange_map:
            # Fallback to hardcoded lists for universes without API support
            hardcoded: dict[str, list[str]] = {
                "dow30": DOW30_CONSTITUENTS,
                "smallcap100": SMALLCAP100_CONSTITUENTS,
            }
            if name in hardcoded:
                return list(hardcoded[name])
            if name in GICS_SECTORS:
                return list(GICS_SECTORS[name])
            logger.warning("Unknown universe: %s", universe_name)
            return []

        params = exchange_map[name]
        try:
            self._throttle()
            tickers = list(
                self._client.list_tickers(
                    market=params["market"],
                    exchange=params.get("exchange"),
                    active=True,
                    limit=1000,
                )
            )
            return [t.ticker for t in tickers if t.ticker]
        except Exception:
            logger.warning(
                "Failed to list universe %s", universe_name, exc_info=True
            )
            return []

    def get_movers(self, direction: str = "gainers", limit: int = 20) -> list[dict]:
        """Get top movers (gainers/losers) via Polygon snapshot endpoint."""
        try:
            self._throttle()
            snapshot = self._client.get_snapshot_direction(
                "stocks", direction, include_otc=False
            )
        except Exception:
            logger.warning(
                "Failed to fetch movers (%s)", direction, exc_info=True
            )
            return []

        results = []
        for item in snapshot[:limit]:
            ticker = item.ticker
            change_pct = 0.0
            price = 0.0
            volume = 0

            if item.todays_change_percent is not None:
                change_pct = float(item.todays_change_percent)
            if item.day and item.day.close:
                price = float(item.day.close)
            if item.day and item.day.volume:
                volume = int(item.day.volume)

            results.append({
                "symbol": ticker,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "price": round(price, 2),
            })

        return results

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _to_polygon_ticker(instrument: Instrument) -> str:
        """Convert instrument to Polygon ticker format (forex uses C: prefix)."""
        from trading.core.models import AssetClass

        if instrument.asset_class == AssetClass.FOREX:
            # EUR/USD → C:EURUSD
            return "C:" + instrument.symbol.replace("/", "")
        return instrument.symbol
