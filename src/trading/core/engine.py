"""Pipeline engine — orchestrates data fetch -> signal -> risk -> order presentation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[str], None] | None

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
                        playbook = self.broker.present_order(
                            order,
                            current_price,
                            conviction=signal.conviction,
                            strategy_name=signal.strategy_name,
                        )

                        results.append({
                            "signal": signal,
                            "order": order,
                            "playbook": playbook,
                        })
            except Exception:
                logger.warning("Failed to process %s, skipping", symbol, exc_info=True)
                continue

        return results

    def discover(
        self,
        symbols: list[str],
        strategy_names: list[str] | None = None,
        lookback_days: int = 120,
        max_results: int = 20,
        on_progress: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Scan a large universe and return top signals ranked by conviction.

        Unlike scan(), this method:
        - Accepts a flat symbol list (caller resolves universe → symbols)
        - Runs only specified strategies (or all registered ones)
        - Sorts results by conviction descending, returns top N
        - Handles forex symbols (containing '/')
        """
        if not symbols:
            return []

        # Filter strategies if specific names requested
        active_strategies = self.strategies
        if strategy_names:
            active_strategies = [
                s for s in self.strategies if s.name in strategy_names
            ]
        if not active_strategies:
            return []

        end = date.today()
        start = end - timedelta(days=lookback_days)
        results = []
        total = len(symbols)

        def _progress(msg: str) -> None:
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        for idx, symbol in enumerate(symbols):
            _progress(f"Scanning {symbol} ({idx + 1}/{total})")

            # Detect asset class from symbol format
            if "/" in symbol:
                asset_class = AssetClass.FOREX
            else:
                asset_class = AssetClass.EQUITY

            instrument = Instrument(symbol=symbol, asset_class=asset_class)

            try:
                bars = self.data_provider.fetch_bars(instrument, start, end)
                if bars.empty:
                    continue

                for strategy in active_strategies:
                    signals = strategy.generate_signals(instrument, bars)

                    for signal in signals:
                        current_price = float(bars["close"].iloc[-1])

                        order = self.risk_manager.evaluate(
                            signal=signal,
                            current_price=current_price,
                            positions=self.positions,
                            cash=self.cash,
                        )

                        if order is None:
                            continue

                        playbook = self.broker.present_order(
                            order,
                            current_price,
                            conviction=signal.conviction,
                            strategy_name=signal.strategy_name,
                        )

                        results.append({
                            "signal": signal,
                            "order": order,
                            "playbook": playbook,
                        })
                        direction = signal.direction.value
                        _progress(
                            f"  Signal: {direction} {symbol} "
                            f"({signal.conviction:.0%} conviction, {strategy.name})"
                        )
            except Exception:
                _progress(f"Failed to process {symbol}, skipping")
                logger.debug("Error details for %s", symbol, exc_info=True)
                continue

        # Rank by conviction descending, return top N
        results.sort(key=lambda r: r["signal"].conviction, reverse=True)
        top = results[:max_results]
        _progress(f"Done — {len(top)} signal{'s' if len(top) != 1 else ''} found from {total} symbols")
        return top

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
