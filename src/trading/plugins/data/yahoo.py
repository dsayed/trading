"""Yahoo Finance data provider plugin."""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from trading.core.models import Instrument


class YahooFinanceProvider:
    """Fetches OHLCV data from Yahoo Finance (free, daily resolution)."""

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
