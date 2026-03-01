"""Yahoo Finance data provider plugin."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import yfinance as yf

from trading.core.models import Instrument, OptionChain, OptionContract

logger = logging.getLogger(__name__)


class YahooFinanceProvider:
    """Fetches OHLCV and options data from Yahoo Finance (free, daily resolution)."""

    @property
    def name(self) -> str:
        return "yahoo"

    def fetch_bars(
        self,
        instrument: Instrument,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        df = yf.download(
            instrument.symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            return df
        # Normalize column names to lowercase
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        # Keep only OHLCV columns
        df = df[["open", "high", "low", "close", "volume"]]
        return df

    def fetch_option_chain(
        self, instrument: Instrument, expiration: date | None = None
    ) -> list[OptionChain]:
        """Fetch option chains for nearest 3 expirations (or a specific one)."""
        ticker = yf.Ticker(instrument.symbol)
        available = ticker.options  # tuple of expiration date strings
        if not available:
            return []

        if expiration is not None:
            exp_strings = [expiration.isoformat()]
        else:
            exp_strings = list(available[:3])

        chains: list[OptionChain] = []
        for exp_str in exp_strings:
            try:
                raw = ticker.option_chain(exp_str)
                exp_date = date.fromisoformat(exp_str)
                calls = [
                    self._row_to_contract(row, exp_date, "call")
                    for _, row in raw.calls.iterrows()
                ]
                puts = [
                    self._row_to_contract(row, exp_date, "put")
                    for _, row in raw.puts.iterrows()
                ]
                chains.append(
                    OptionChain(
                        instrument=instrument,
                        expiration=exp_date,
                        calls=calls,
                        puts=puts,
                    )
                )
            except Exception:
                logger.warning(
                    "Failed to fetch option chain for %s exp %s",
                    instrument.symbol, exp_str, exc_info=True,
                )
                continue
        return chains

    def fetch_current_price(self, instrument: Instrument) -> float:
        """Fetch the latest price for an instrument."""
        ticker = yf.Ticker(instrument.symbol)
        return float(ticker.fast_info["lastPrice"])

    @staticmethod
    def _row_to_contract(
        row: pd.Series, expiration: date, option_type: str
    ) -> OptionContract:
        return OptionContract(
            contract_symbol=str(row.get("contractSymbol", "")),
            strike=float(row["strike"]),
            expiration=expiration,
            option_type=option_type,
            bid=float(row.get("bid", 0)),
            ask=float(row.get("ask", 0)),
            last_price=float(row.get("lastPrice", 0)),
            volume=int(row.get("volume", 0) or 0) if not pd.isna(row.get("volume")) else 0,
            open_interest=int(row.get("openInterest", 0) or 0) if not pd.isna(row.get("openInterest")) else 0,
            implied_volatility=float(row.get("impliedVolatility", 0)) if not pd.isna(row.get("impliedVolatility")) else 0.0,
            in_the_money=bool(row.get("inTheMoney", False)),
        )
