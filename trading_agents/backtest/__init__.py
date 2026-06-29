"""Backtesting engine and portfolio simulation."""

from trading_agents.backtest.engine import Backtester, BacktestResult
from trading_agents.backtest.metrics import PerformanceMetrics, compute_metrics
from trading_agents.backtest.portfolio import Portfolio
from trading_agents.backtest.strategies import (
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
