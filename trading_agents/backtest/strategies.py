"""Strategies the backtester can drive.

A strategy maps a *slice* of price history (everything known up to the decision
date) to a :class:`~trading_agents.agents.schemas.TradeDecision`. This is exactly
the contract the multi-agent pipeline already satisfies, so the agents plug
straight into the backtester. Two simple baselines are provided for comparison.
"""

from __future__ import annotations

from typing import Protocol

from trading_agents.agents.schemas import Action, TradeDecision
from trading_agents.data.indicators import sma
from trading_agents.data.types import PriceHistory
from trading_agents.orchestration.pipeline import TradingPipeline


class Strategy(Protocol):
    name: str

    def decide(self, history: PriceHistory) -> TradeDecision: ...


class AgentStrategy:
    """Drive the full multi-agent pipeline inside the backtester."""

    name = "multi_agent"

    def __init__(self, pipeline: TradingPipeline):
        self.pipeline = pipeline

    def decide(self, history: PriceHistory) -> TradeDecision:
        return self.pipeline.analyze_history(history).decision


class BuyAndHold:
    name = "buy_and_hold"

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        return TradeDecision(
            symbol=history.symbol,
            action=Action.BUY,
            target_weight=self.weight,
            confidence=1.0,
            rationale="Always fully invested.",
        )


class MovingAverageCrossover:
    """Classic baseline: long when fast SMA > slow SMA, flat otherwise."""

    name = "sma_crossover"

    def __init__(self, fast: int = 20, slow: int = 50, weight: float = 1.0):
        self.fast = fast
        self.slow = slow
        self.weight = weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        close = history.frame["close"]
        fast = float(sma(close, self.fast).iloc[-1])
        slow = float(sma(close, self.slow).iloc[-1])
        if fast > slow:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=self.weight,
                confidence=0.6,
                rationale=f"Fast SMA {fast:.2f} > slow SMA {slow:.2f}.",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.SELL,
            target_weight=0.0,
            confidence=0.6,
            rationale=f"Fast SMA {fast:.2f} <= slow SMA {slow:.2f}.",
        )
