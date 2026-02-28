"""CLI entry point for the trading system."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading.core.config import TradingConfig, load_config
from trading.core.engine import TradingEngine
from trading.plugins.brokers.manual import ManualBroker
from trading.plugins.data.yahoo import YahooFinanceProvider
from trading.plugins.risk.fixed_stake import FixedStakeRiskManager
from trading.plugins.strategies.momentum import MomentumStrategy

app = typer.Typer(help="Hybrid trading system — automated signals, manual execution.")
console = Console()


@app.callback()
def main() -> None:
    """Hybrid trading system — automated signals, manual execution."""


def _build_engine(config_path: Path = Path("config.toml")) -> TradingEngine:
    """Build the trading engine from config, wiring up all plugins."""
    config = load_config(config_path)

    data_provider = YahooFinanceProvider()

    strategy_map = {
        "momentum": MomentumStrategy,
    }
    strategies = [strategy_map[name]() for name in config.strategies if name in strategy_map]

    risk_manager = FixedStakeRiskManager(
        stake=config.stake,
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
    )

    broker = ManualBroker()

    return TradingEngine(
        data_provider=data_provider,
        strategies=strategies,
        risk_manager=risk_manager,
        broker=broker,
        config=config,
    )


@app.command()
def scan(
    explain: Optional[str] = typer.Option(
        None, "--explain", help="Show full playbook for a specific symbol"
    ),
    config: Path = typer.Option(
        Path("config.toml"), "--config", "-c", help="Path to config file"
    ),
) -> None:
    """Run the pipeline and show today's signals."""
    engine = _build_engine(config)

    symbols = [explain] if explain else None
    results = engine.scan(symbols=symbols)

    if not results:
        console.print("\n[dim]No actionable signals found today.[/dim]\n")
        return

    if explain:
        for result in results:
            sig = result["signal"]
            console.print()
            console.print(
                Panel(
                    result["playbook"],
                    title=f"[bold]{sig.direction.value.upper()} {sig.instrument.symbol}[/bold]",
                    subtitle=f"conviction: {sig.conviction:.0%} | strategy: {sig.strategy_name}",
                )
            )
            console.print(f"\n[bold]Rationale:[/bold] {sig.rationale}\n")
        return

    table = Table(title="Today's Signals")
    table.add_column("Action", style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Conviction")
    table.add_column("Qty")
    table.add_column("Limit Price")
    table.add_column("Strategy")
    table.add_column("Summary")

    for result in results:
        sig = result["signal"]
        order = result["order"]
        direction = sig.direction.value.upper()

        if sig.direction.value == "long":
            style = "green"
        elif sig.direction.value == "close":
            style = "red"
        else:
            style = "yellow"

        summary = sig.rationale[:60] + "..." if len(sig.rationale) > 60 else sig.rationale

        table.add_row(
            f"[{style}]{direction}[/{style}]",
            sig.instrument.symbol,
            f"{sig.conviction:.0%}",
            str(order.quantity),
            f"${order.limit_price:.2f}" if order.limit_price else "—",
            sig.strategy_name,
            summary,
        )

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Use [bold]trading scan --explain SYMBOL[/bold] for full playbook.[/dim]\n"
    )
