"""Backtesting engine and portfolio simulation."""

from stock_trading_agent.backtest.engine import Backtester, BacktestResult
from stock_trading_agent.backtest.metrics import PerformanceMetrics, compute_metrics
from stock_trading_agent.backtest.portfolio import Portfolio
from stock_trading_agent.backtest.strategies import (
    AgentStrategy,
    BollingerBreakoutStrategy,
    BuyAndHold,
    EnsembleStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossover,
    Strategy,
)

#: Registry of baseline strategies that need no constructor arguments, keyed by
#: their public ``name``. Used by the CLI and API to build comparison sets.
BASELINE_STRATEGIES = {
    cls.name: cls
    for cls in (
        MovingAverageCrossover,
        MomentumStrategy,
        MeanReversionStrategy,
        BollingerBreakoutStrategy,
        EnsembleStrategy,
        BuyAndHold,
    )
}

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
    "MomentumStrategy",
    "MeanReversionStrategy",
    "BollingerBreakoutStrategy",
    "EnsembleStrategy",
    "BASELINE_STRATEGIES",
]
