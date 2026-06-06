from __future__ import annotations

from trading_agents.core.blackboard import PipelineContext
from trading_agents.schemas import MarketAnalysis, TradeAction
from trading_agents.tools.market_data import MarketDataProvider


class MarketAnalyst:
    agent_id = "market_analyst"

    def __init__(self, market_data: MarketDataProvider) -> None:
        self.market_data = market_data

    async def analyze(self, ctx: PipelineContext) -> MarketAnalysis:
        snapshot = ctx.snapshot or await self.market_data.get_snapshot(ctx.symbol)
        bars = await self.market_data.get_bars(ctx.symbol, limit=30)

        if len(bars) < 10:
            return MarketAnalysis(
                symbol=ctx.symbol,
                direction=TradeAction.HOLD,
                confidence=0.3,
                rationale="Insufficient data for technical analysis",
            )

        closes = [b["close"] for b in bars]
        sma_short = sum(closes[-5:]) / 5
        sma_long = sum(closes[-20:]) / 20
        momentum = (closes[-1] - closes[-10]) / closes[-10]

        if sma_short > sma_long and momentum > 0.01:
            direction, confidence = TradeAction.BUY, min(0.5 + abs(momentum) * 5, 0.85)
            rationale = f"Bullish: SMA5 ({sma_short:.2f}) > SMA20 ({sma_long:.2f}), momentum {momentum:.2%}"
        elif sma_short < sma_long and momentum < -0.01:
            direction, confidence = TradeAction.SELL, min(0.5 + abs(momentum) * 5, 0.85)
            rationale = f"Bearish: SMA5 ({sma_short:.2f}) < SMA20 ({sma_long:.2f}), momentum {momentum:.2%}"
        else:
            direction, confidence = TradeAction.HOLD, 0.45
            rationale = "No clear trend signal"

        return MarketAnalysis(
            symbol=ctx.symbol,
            direction=direction,
            confidence=confidence,
            support_level=min(closes[-20:]),
            resistance_level=max(closes[-20:]),
            indicators={"sma5": sma_short, "sma20": sma_long, "momentum": momentum},
            rationale=rationale,
        )
