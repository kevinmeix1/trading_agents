"""Command-line interface for stock_trading_agent.

Examples
--------
    stock-trading-agent analyze AAPL
    stock-trading-agent analyze TSLA --news "beats earnings" --news "analyst upgrade"
    stock-trading-agent backtest NVDA --days 500 --compare
    stock-trading-agent config
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stock_trading_agent import __version__
from stock_trading_agent.config import DataSource, LLMProvider, Settings, get_settings

app = typer.Typer(
    add_completion=False,
    help="An advanced multi-agent AI system for financial trading research.",
)
console = Console()


def _settings(verbose: bool) -> Settings:
    base = get_settings()
    return base.model_copy(update={"verbose": verbose})


@app.command()
def analyze(
    symbol: str = typer.Argument(..., help="Ticker to analyze, e.g. AAPL."),
    days: int = typer.Option(365, help="Lookback window in days."),
    news: list[str] = typer.Option(None, "--news", help="Optional headline(s)."),
    debate_rounds: int = typer.Option(2, help="Bull/bear debate rounds."),
    record: bool = typer.Option(False, help="Persist this decision to memory."),
    verbose: bool = typer.Option(True, help="Stream agent-by-agent reasoning."),
) -> None:
    """Run the full multi-agent pipeline for a single symbol."""

    from stock_trading_agent.orchestration import TradingPipeline

    settings = _settings(verbose)
    pipeline = TradingPipeline(settings, debate_rounds=debate_rounds)
    result = pipeline.analyze(symbol, lookback_days=days, news=news, record=record)

    table = Table(title=f"Analyst Reports — {result.symbol}", show_lines=False)
    table.add_column("Analyst", style="cyan")
    table.add_column("Stance")
    table.add_column("Signal", justify="right")
    table.add_column("Conf", justify="right")
    table.add_column("Rationale", overflow="fold")
    for r in result.reports:
        color = "green" if r.signal > 0 else "red" if r.signal < 0 else "yellow"
        table.add_row(
            r.agent,
            f"[{color}]{r.stance}[/{color}]",
            f"{r.signal:+.2f}",
            f"{r.confidence:.2f}",
            r.rationale,
        )
    console.print(table)

    if result.debate:
        console.print(
            Panel(
                f"[bold green]BULL[/bold green]\n{result.debate.bull_thesis}\n\n"
                f"[bold red]BEAR[/bold red]\n{result.debate.bear_thesis}\n\n"
                f"[bold]JUDGE[/bold] {result.debate.judge_summary}",
                title="Research Debate",
            )
        )

    d = result.decision
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[d.action.value]
    console.print(
        Panel(
            f"[bold {color}]{d.action.value}[/bold {color}]  "
            f"target weight [bold]{d.target_weight:.1%}[/bold]  "
            f"confidence [bold]{d.confidence:.2f}[/bold]\n"
            f"stop {d.stop_loss_pct:.0%} / target {d.take_profit_pct:.0%}\n\n{d.rationale}",
            title=f"FINAL DECISION — {result.symbol}",
            border_style=color,
        )
    )


@app.command()
def backtest(
    symbol: str = typer.Argument(..., help="Ticker to backtest."),
    days: int = typer.Option(500, help="History length in days."),
    rebalance_every: int = typer.Option(21, help="Rebalance frequency (days)."),
    compare: bool = typer.Option(True, help="Compare against baseline strategies."),
) -> None:
    """Backtest the multi-agent strategy (optionally vs baselines)."""

    from stock_trading_agent.backtest import (
        AgentStrategy,
        Backtester,
        BollingerBreakoutStrategy,
        BuyAndHold,
        EnsembleStrategy,
        MeanReversionStrategy,
        MomentumStrategy,
        MovingAverageCrossover,
    )
    from stock_trading_agent.data.market import get_market_provider
    from stock_trading_agent.orchestration import TradingPipeline

    settings = _settings(verbose=False)
    history = get_market_provider(settings).history(symbol, lookback_days=days)
    engine = Backtester(rebalance_every=rebalance_every)

    strategies = [AgentStrategy(TradingPipeline(settings))]
    if compare:
        strategies += [
            MomentumStrategy(),
            MeanReversionStrategy(),
            BollingerBreakoutStrategy(),
            EnsembleStrategy(),
            MovingAverageCrossover(),
            BuyAndHold(),
        ]

    table = Table(title=f"Backtest — {symbol.upper()} ({days}d)")
    for col in ("Strategy", "Total", "CAGR", "Sharpe", "Sortino", "MaxDD", "WinRate", "Trades"):
        table.add_column(col, justify="right" if col != "Strategy" else "left")

    with console.status("Running backtests..."):
        for strat in strategies:
            r = engine.run(history, strat)
            m = r.metrics
            table.add_row(
                r.strategy,
                f"{m.total_return:+.1%}",
                f"{m.cagr:+.1%}",
                f"{m.sharpe:.2f}",
                f"{m.sortino:.2f}",
                f"{m.max_drawdown:.1%}",
                f"{m.win_rate:.0%}",
                str(len(r.trades)),
            )
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind."),
    port: int = typer.Option(8000, help="Port to listen on."),
) -> None:
    """Launch the web dashboard + REST API (requires the ``web`` extra)."""

    from stock_trading_agent.api import run

    console.print(
        Panel(
            f"Starting the Stock Trading Agent dashboard on "
            f"[bold cyan]http://{host}:{port}[/bold cyan]\n"
            "Open it in your browser to analyse symbols and run backtests.",
                title="Stock Trading Agent — serve",
            border_style="cyan",
        )
    )
    run(host=host, port=port)


@app.command()
def config() -> None:
    """Show the active configuration."""

    s = get_settings()
    table = Table(title="Stock Trading Agent — configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("version", __version__)
    table.add_row("llm_provider", s.llm_provider.value)
    table.add_row("llm_model", s.llm_model)
    table.add_row("data_source", s.data_source.value)
    table.add_row("memory_path", s.memory_path)
    offline = s.llm_provider == LLMProvider.OFFLINE
    table.add_row("mode", "offline (deterministic)" if offline else "live LLM")
    table.add_row(
        "data",
        "synthetic (no network)" if s.data_source == DataSource.SYNTHETIC else "yfinance",
    )
    console.print(table)


@app.command()
def version() -> None:
    """Print the version."""

    console.print(f"stock_trading_agent {__version__}")


if __name__ == "__main__":
    app()
