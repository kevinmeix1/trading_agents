"""Event-driven, walk-forward backtester for a single symbol.

The engine steps day by day. On rebalance days it shows the strategy only the
history available *up to that day* (no look-ahead), gets a decision and adjusts
the position. Every day it marks to market and checks stop-loss / take-profit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from stock_trading_agent.agents.schemas import Action, TradeDecision
from stock_trading_agent.backtest.metrics import PerformanceMetrics, compute_metrics
from stock_trading_agent.backtest.portfolio import Portfolio
from stock_trading_agent.data.types import PriceHistory

if TYPE_CHECKING:
    from stock_trading_agent.backtest.strategies import Strategy


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    equity_curve: pd.Series
    metrics: PerformanceMetrics
    trades: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        m = self.metrics
        return (
            f"[{self.strategy}] {self.symbol}: total {m.total_return:+.1%} | "
            f"CAGR {m.cagr:+.1%} | Sharpe {m.sharpe:.2f} | maxDD {m.max_drawdown:.1%}"
        )


class Backtester:
    def __init__(
        self,
        *,
        initial_cash: float = 100_000.0,
        commission: float = 0.0005,
        rebalance_every: int = 21,
        warmup: int = 60,
    ):
        self.initial_cash = initial_cash
        self.commission = commission
        self.rebalance_every = max(1, rebalance_every)
        self.warmup = max(2, warmup)

    def run(self, history: PriceHistory, strategy: Strategy) -> BacktestResult:
        frame = history.frame
        symbol = history.symbol
        portfolio = Portfolio(cash=self.initial_cash, commission=self.commission)

        equity_points: list[tuple[pd.Timestamp, float]] = []
        trades: list[dict] = []

        n = len(frame)
        for i in range(n):
            row = frame.iloc[i]
            ts = frame.index[i]
            price = float(row["close"])
            prices = {symbol: price}

            for exited in portfolio.check_exits(prices):
                trades.append({"date": str(ts.date()), "symbol": exited, "action": "EXIT"})

            is_rebalance = i >= self.warmup and (i - self.warmup) % self.rebalance_every == 0
            if is_rebalance:
                window = PriceHistory(symbol=symbol, frame=frame.iloc[: i + 1].copy())
                decision: TradeDecision = strategy.decide(window)
                if decision.action == Action.BUY:
                    portfolio.rebalance(
                        symbol,
                        decision.target_weight,
                        price,
                        stop_loss_pct=decision.stop_loss_pct,
                        take_profit_pct=decision.take_profit_pct,
                    )
                    trades.append(
                        {
                            "date": str(ts.date()),
                            "symbol": symbol,
                            "action": "BUY",
                            "weight": round(decision.target_weight, 4),
                        }
                    )
                elif decision.action == Action.SELL:
                    portfolio.rebalance(symbol, 0.0, price)
                    trades.append(
                        {"date": str(ts.date()), "symbol": symbol, "action": "SELL", "weight": 0.0}
                    )
                # HOLD: leave the position untouched.

            equity_points.append((ts, portfolio.equity(prices)))

        equity_curve = pd.Series(
            [v for _, v in equity_points],
            index=pd.DatetimeIndex([t for t, _ in equity_points]),
            name="equity",
        )
        metrics = compute_metrics(equity_curve)
        return BacktestResult(
            symbol=symbol,
            strategy=getattr(strategy, "name", strategy.__class__.__name__),
            equity_curve=equity_curve,
            metrics=metrics,
            trades=trades,
        )
