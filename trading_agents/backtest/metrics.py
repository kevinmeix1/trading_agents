"""Performance metrics for an equity curve."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class PerformanceMetrics:
    total_return: float
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    num_days: int

    def to_dict(self) -> dict:
        return asdict(self)


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def compute_metrics(equity_curve: pd.Series, risk_free: float = 0.0) -> PerformanceMetrics:
    """Compute standard performance stats from an equity curve (indexed by date)."""

    equity = equity_curve.dropna()
    if len(equity) < 2:
        return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, len(equity))

    returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    years = max(len(equity) / TRADING_DAYS, 1e-9)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0)

    ann_vol = float(returns.std(ddof=0) * np.sqrt(TRADING_DAYS))
    excess = returns - risk_free / TRADING_DAYS
    sharpe = float(excess.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS)) if returns.std(ddof=0) else 0.0

    downside = returns[returns < 0]
    downside_std = float(downside.std(ddof=0)) if len(downside) else 0.0
    sortino = float(excess.mean() / downside_std * np.sqrt(TRADING_DAYS)) if downside_std else 0.0

    mdd = _max_drawdown(equity)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0
    win_rate = float((returns > 0).mean())

    return PerformanceMetrics(
        total_return=round(total_return, 4),
        cagr=round(cagr, 4),
        annual_volatility=round(ann_vol, 4),
        sharpe=round(sharpe, 3),
        sortino=round(sortino, 3),
        max_drawdown=round(mdd, 4),
        calmar=round(calmar, 3),
        win_rate=round(win_rate, 4),
        num_days=len(equity),
    )
