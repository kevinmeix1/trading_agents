"""Backtesting engine and portfolio simulation."""

from trading_agents.backtest.engine import Backtester, BacktestResult
from trading_agents.backtest.metrics import PerformanceMetrics, compute_metrics
from trading_agents.backtest.portfolio import Portfolio
from trading_agents.backtest.strategies import (
    AgentStrategy,
    BuyAndHold,
    MovingAverageCrossover,
    Strategy,
)

__all__ = [
    "Backtester",
    "BacktestResult",
    "Portfolio",
    "PerformanceMetrics",
    "compute_metrics",
    "Strategy",
    "AgentStrategy",
    "BuyAndHold",
    "MovingAverageCrossover",
]
