"""Twelve Data provider plugin.

Implements DataProvider and OptionsDataProvider protocols.
Uses the official twelvedata SDK (well-maintained, DataFrame output).
Requires TWELVEDATA_API_KEY environment variable or passed directly.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import pandas as pd

from trading.core.models import Instrument, OptionChain, OptionContract

logger = logging.getLogger(__name__)


class TwelveDataProvider:
    """Fetches market data from Twelve Data via the official SDK.

    Implements DataProvider and OptionsDataProvider protocols.
    Twelve Data has broad global coverage (stocks, forex, crypto, ETFs)
    and the SDK returns pandas DataFrames natively.
    """

    def __init__(
        self, api_key: str | None = None, calls_per_minute: int = 8
    ) -> None:
        from twelvedata import TDClient

        key = api_key or os.environ.get("TWELVEDATA_API_KEY", "")
        if not key:
            raise ValueError(
                "Twelve Data API key required. Set TWELVEDATA_API_KEY env var "
                "or pass api_key to TwelveDataProvider."
            )
        self._client = TDClient(apikey=key)
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

    @property
    def name(self) -> str:
        return "twelvedata"

    # ── DataProvider ──────────────────────────────────────────────────

    def fetch_bars(
        self, instrument: Instrument, start: date, end: date
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars via Twelve Data time_series endpoint."""
        try:
            self._throttle()
            ts = self._client.time_series(
                symbol=instrument.symbol,
                interval="1day",
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                outputsize=5000,
            )
            df = ts.as_pandas()
        except Exception:
            logger.warning(
                "Failed to fetch bars for %s", instrument.symbol, exc_info=True
            )
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # Normalize column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Keep only OHLCV columns
        expected = ["open", "high", "low", "close", "volume"]
        available = [c for c in expected if c in df.columns]
        df = df[available]

        # Ensure numeric types
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_index()
        return df

    # ── OptionsDataProvider ───────────────────────────────────────────

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        """Fetch option chains via Twelve Data options endpoint."""
        try:
            self._throttle()
            params: dict = {"symbol": instrument.symbol}
            if expiration:
                params["expiration_date"] = expiration.isoformat()

            data = self._client.options_chain(**params).as_json()
        except Exception:
            logger.warning(
                "Failed to fetch option chain for %s",
                instrument.symbol, exc_info=True,
            )
            return []

        if not data:
            return []

        # Twelve Data returns a list of contracts — group by expiration
        contracts = data if isinstance(data, list) else data.get("options", [])
        by_expiration: dict[date, dict[str, list[OptionContract]]] = {}

        for c in contracts:
            exp_str = c.get("expiration_date", "")
            if not exp_str:
                continue
            exp = date.fromisoformat(exp_str[:10])
            if exp not in by_expiration:
                by_expiration[exp] = {"calls": [], "puts": []}

            opt = OptionContract(
                contract_symbol=c.get("contract_name", ""),
                strike=float(c.get("strike", 0)),
                expiration=exp,
                option_type=c.get("option_type", "call").lower(),
                bid=float(c.get("bid", 0)),
                ask=float(c.get("ask", 0)),
                last_price=float(c.get("last_price", 0) or c.get("close", 0)),
                volume=int(c.get("volume", 0) or 0),
                open_interest=int(c.get("open_interest", 0) or 0),
                implied_volatility=float(c.get("implied_volatility", 0) or 0),
                in_the_money=bool(c.get("in_the_money", False)),
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
        """Fetch latest price via Twelve Data price endpoint."""
        try:
            self._throttle()
            data = self._client.price(symbol=instrument.symbol).as_json()
            if data and "price" in data:
                return float(data["price"])
            return 0.0
        except Exception:
            logger.warning(
                "Failed to fetch current price for %s",
                instrument.symbol, exc_info=True,
            )
            return 0.0
