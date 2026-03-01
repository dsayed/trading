"""CLI entry point for the trading system."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trading.core.config import load_config
from trading.core.engine import TradingEngine
from trading.core.factory import build_engine
from trading.plugins.data.base import DiscoveryProvider

app = typer.Typer(help="Hybrid trading system — automated signals, manual execution.")
console = Console()


@app.callback()
def main() -> None:
    """Hybrid trading system — automated signals, manual execution."""


def _build_engine(config_path: Path = Path("config.toml")) -> TradingEngine:
    """Build the trading engine from config, wiring up all plugins."""
    config = load_config(config_path)
    return build_engine(config)


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


@app.command()
def discover(
    universe: Optional[str] = typer.Option(
        None, "--universe", "-u", help="Universe to scan (sp500, nasdaq100, forex_majors, gainers, losers)"
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", "-s", help="Comma-separated symbols to scan"
    ),
    strategy: Optional[str] = typer.Option(
        None, "--strategy", help="Comma-separated strategy names"
    ),
    top: int = typer.Option(20, "--top", "-t", help="Max results to return"),
    config: Path = typer.Option(
        Path("config.toml"), "--config", "-c", help="Path to config file"
    ),
) -> None:
    """Discover opportunities across a market universe."""
    engine = _build_engine(config)

    # Resolve symbols
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    elif universe:
        if not isinstance(engine.data_provider, DiscoveryProvider):
            console.print(
                f"\n[red]Data provider '{engine.config.data_provider}' does not support "
                f"universe discovery. Use --symbols or set data_provider = 'polygon'.[/red]\n"
            )
            raise typer.Exit(1)

        name = universe.lower()
        if name in ("gainers", "losers"):
            movers = engine.data_provider.get_movers(name, limit=top)
            symbol_list = [m["symbol"] for m in movers]
            if movers:
                console.print(f"\n[dim]Top {name}: {', '.join(symbol_list[:10])}...[/dim]")
        else:
            symbol_list = engine.data_provider.list_universe(name)

        if not symbol_list:
            console.print(f"\n[red]No symbols found for universe '{universe}'.[/red]\n")
            raise typer.Exit(1)

        console.print(f"\n[dim]Scanning {len(symbol_list)} symbols from '{universe}'...[/dim]")
    else:
        console.print("\n[red]Provide --universe or --symbols.[/red]\n")
        raise typer.Exit(1)

    strategy_names = [s.strip() for s in strategy.split(",")] if strategy else None

    results = engine.discover(
        symbols=symbol_list,
        strategy_names=strategy_names,
        max_results=top,
    )

    if not results:
        console.print("\n[dim]No actionable signals found.[/dim]\n")
        return

    table = Table(title=f"Top {len(results)} Opportunities")
    table.add_column("#", style="dim")
    table.add_column("Action", style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Conviction")
    table.add_column("Qty")
    table.add_column("Strategy")
    table.add_column("Summary")

    for rank, result in enumerate(results, 1):
        sig = result["signal"]
        order = result["order"]
        direction = sig.direction.value.upper()

        if sig.direction.value == "long":
            style = "green"
        elif sig.direction.value == "close":
            style = "red"
        else:
            style = "yellow"

        summary = sig.rationale[:55] + "..." if len(sig.rationale) > 55 else sig.rationale

        table.add_row(
            str(rank),
            f"[{style}]{direction}[/{style}]",
            sig.instrument.symbol,
            f"{sig.conviction:.0%}",
            str(order.quantity),
            sig.strategy_name,
            summary,
        )

    console.print()
    console.print(table)
    console.print()
