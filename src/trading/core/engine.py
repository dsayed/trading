"""Pipeline engine — orchestrates data fetch -> signal -> risk -> order presentation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from trading.core.config import TradingConfig
from trading.core.models import AssetClass, Instrument, Position


class TradingEngine:
    """Wires plugins together and runs the trading pipeline."""

    def __init__(
        self,
        data_provider: Any,
        strategies: list[Any],
        risk_manager: Any,
        broker: Any,
        config: TradingConfig,
        positions: list[Position] | None = None,
        cash: float | None = None,
    ) -> None:
        self.data_provider = data_provider
        self.strategies = strategies
        self.risk_manager = risk_manager
        self.broker = broker
        self.config = config
        self.positions = positions or []
        self.cash = cash if cash is not None else config.stake

    def scan(
        self,
        symbols: list[str] | None = None,
        lookback_days: int = 120,
    ) -> list[dict[str, Any]]:
        """Run the full pipeline for the watchlist (or a subset of symbols)."""
        target_symbols = symbols or self.config.watchlist
        if not target_symbols:
            return []

        end = date.today()
        start = end - timedelta(days=lookback_days)
        results = []

        for symbol in target_symbols:
            instrument = Instrument(symbol=symbol, asset_class=AssetClass.EQUITY)

            # Stage 1: Fetch data
            bars = self.data_provider.fetch_bars(instrument, start, end)
            if bars.empty:
                continue

            # Stage 2: Generate signals from all strategies
            for strategy in self.strategies:
                signals = strategy.generate_signals(instrument, bars)

                for signal in signals:
                    current_price = float(bars["close"].iloc[-1])

                    # Stage 3: Risk filtering and sizing
                    order = self.risk_manager.evaluate(
                        signal=signal,
                        current_price=current_price,
                        positions=self.positions,
                        cash=self.cash,
                    )

                    if order is None:
                        continue

                    # Stage 4: Generate playbook
                    playbook = self.broker.present_order(order, current_price)

                    results.append({
                        "signal": signal,
                        "order": order,
                        "playbook": playbook,
                    })

        return results
