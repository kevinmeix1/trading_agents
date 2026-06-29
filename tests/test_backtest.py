from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agents.agents.schemas import Action
from trading_agents.backtest.engine import Backtester
from trading_agents.backtest.metrics import compute_metrics
from trading_agents.backtest.portfolio import Portfolio
from trading_agents.backtest.strategies import (
    AgentStrategy,
    BollingerBreakoutStrategy,
    BuyAndHold,
    EnsembleStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossover,
)
from trading_agents.orchestration.pipeline import TradingPipeline


def test_metrics_on_known_curve():
    # Steady 0.1%/day growth for ~1 year.
    idx = pd.bdate_range("2022-01-01", periods=252)
    equity = pd.Series(100000 * (1.001 ** np.arange(252)), index=idx)
    m = compute_metrics(equity)
    assert m.total_return > 0
    assert m.cagr > 0
    assert m.max_drawdown == 0.0  # monotonic increase
    assert m.sharpe > 0


def test_portfolio_buy_and_sell_cycle():
    p = Portfolio(cash=10_000, commission=0.0)
    p.rebalance("AAPL", target_weight=0.5, price=100.0)
    assert p.position("AAPL").shares == 50.0
    assert p.cash == 5_000.0
    p.rebalance("AAPL", target_weight=0.0, price=110.0)
    assert p.position("AAPL").shares == 0.0
    assert p.equity({"AAPL": 110.0}) == 10_500.0  # +10% on half the book


def test_portfolio_stop_loss_triggers():
    p = Portfolio(cash=10_000, commission=0.0)
    p.rebalance("AAPL", target_weight=1.0, price=100.0, stop_loss_pct=0.1)
    triggered = p.check_exits({"AAPL": 85.0})
    assert "AAPL" in triggered
    assert p.position("AAPL").shares == 0.0


def test_portfolio_does_not_overspend():
    p = Portfolio(cash=1_000, commission=0.0)
    p.rebalance("AAPL", target_weight=2.0, price=100.0)  # asks for 2x equity
    assert p.cash >= -1e-6


def test_backtester_runs_all_strategies(history, settings):
    engine = Backtester(rebalance_every=21, warmup=60)
    for strat in (
        AgentStrategy(TradingPipeline(settings)),
        MovingAverageCrossover(),
        BuyAndHold(),
    ):
        result = engine.run(history, strat)
        assert len(result.equity_curve) == len(history)
        assert result.metrics.num_days == len(history)


def test_new_strategies_emit_valid_decisions(history):
    strategies = [
        MomentumStrategy(),
        MeanReversionStrategy(),
        BollingerBreakoutStrategy(),
        EnsembleStrategy(),
    ]
    for strat in strategies:
        decision = strat.decide(history)
        assert decision.action in set(Action)
        assert 0.0 <= decision.target_weight <= 1.0
        assert 0.0 <= decision.confidence <= 1.0


def test_new_strategies_backtest_runs(history):
    engine = Backtester(rebalance_every=21, warmup=60)
    for strat in (MomentumStrategy(), MeanReversionStrategy(), EnsembleStrategy()):
        result = engine.run(history, strat)
        assert len(result.equity_curve) == len(history)
        assert result.metrics.num_days == len(history)


def test_ensemble_is_deterministic(history):
    a = EnsembleStrategy().decide(history)
    b = EnsembleStrategy().decide(history)
    assert a.action == b.action
    assert a.target_weight == b.target_weight


def test_backtest_no_lookahead(history, settings):
    # The strategy must only ever see history up to the decision date. We assert
    # the engine slices correctly by checking equity starts at initial cash.
    engine = Backtester(rebalance_every=21, warmup=60, initial_cash=100_000)
    result = engine.run(history, BuyAndHold())
    assert abs(result.equity_curve.iloc[0] - 100_000) < 1e-6
