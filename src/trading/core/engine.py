"""Pipeline engine — orchestrates data fetch -> signal -> risk -> order presentation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from trading.core.config import TradingConfig
from trading.core.models import AssetClass, Instrument, Position
from trading.plugins.data.base import OptionsDataProvider

logger = logging.getLogger(__name__)


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

            try:
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
            except Exception:
                logger.warning("Failed to process %s, skipping", symbol, exc_info=True)
                continue

        return results

    def advise(
        self,
        positions: list[Position],
        advisors: list[Any],
        lookback_days: int = 120,
    ) -> list[dict[str, Any]]:
        """Run advisor pipeline: for each position, gather data and collect plays."""
        if not positions or not advisors:
            return []

        end = date.today()
        start = end - timedelta(days=lookback_days)
        results = []
        supports_options = isinstance(self.data_provider, OptionsDataProvider)

        for position in positions:
            try:
                bars = self.data_provider.fetch_bars(position.instrument, start, end)
                if bars.empty:
                    current_price = 0.0
                else:
                    current_price = float(bars["close"].iloc[-1])

                option_chains = []
                if supports_options:
                    try:
                        option_chains = self.data_provider.fetch_option_chain(
                            position.instrument
                        )
                    except Exception:
                        logger.warning(
                            "Failed to fetch option chains for %s",
                            position.instrument.symbol,
                            exc_info=True,
                        )

                all_plays = []
                for advisor in advisors:
                    plays = advisor.advise(
                        position, bars, option_chains, current_price
                    )
                    all_plays.extend(plays)

                pnl = position.unrealized_pnl(current_price) if current_price > 0 else 0.0

                results.append({
                    "position": position,
                    "current_price": current_price,
                    "unrealized_pnl": pnl,
                    "plays": all_plays,
                })
            except Exception:
                logger.warning(
                    "Failed to advise on %s, skipping",
                    position.instrument.symbol,
                    exc_info=True,
                )
                continue

        return results
