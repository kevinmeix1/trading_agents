from __future__ import annotations

from trading_agents.config import MarketRegime, settings
from trading_agents.core.blackboard import PipelineContext
from trading_agents.schemas import DebateArgument, DebateVerdict, TradeAction


class BullAgent:
    agent_id = "bull_agent"

    async def argue(self, ctx: PipelineContext) -> DebateArgument:
        points: list[str] = []
        confidence = 0.5

        if ctx.market_analysis and ctx.market_analysis.direction == TradeAction.BUY:
            points.append(ctx.market_analysis.rationale)
            confidence = max(confidence, ctx.market_analysis.confidence)

        if ctx.sentiment and ctx.sentiment.score > 0:
            points.append(f"Sentiment bullish: {ctx.sentiment.summary}")
            confidence = max(confidence, ctx.sentiment.confidence * 0.9)

        if ctx.regime == MarketRegime.TRENDING:
            points.append("Trending regime favors momentum longs")

        if not points:
            points.append("No strong bullish case; mild opportunistic bias")

        return DebateArgument(
            agent_id=self.agent_id,
            stance=TradeAction.BUY,
            confidence=min(confidence, 0.9),
            key_points=points,
        )


class BearAgent:
    agent_id = "bear_agent"

    async def argue(self, ctx: PipelineContext) -> DebateArgument:
        points: list[str] = []
        confidence = 0.5

        if ctx.market_analysis and ctx.market_analysis.direction == TradeAction.SELL:
            points.append(ctx.market_analysis.rationale)
            confidence = max(confidence, ctx.market_analysis.confidence)

        if ctx.sentiment and ctx.sentiment.score < 0:
            points.append(f"Sentiment bearish: {ctx.sentiment.summary}")
            confidence = max(confidence, ctx.sentiment.confidence * 0.9)

        if ctx.regime in (MarketRegime.HIGH_VOLATILITY, MarketRegime.CRISIS):
            points.append(f"{ctx.regime.value} regime — reduce exposure, favor cash")
            confidence = max(confidence, 0.75)

        if not points:
            points.append("No strong bearish case; default risk-off bias in uncertainty")

        return DebateArgument(
            agent_id=self.agent_id,
            stance=TradeAction.SELL if ctx.regime != MarketRegime.CRISIS else TradeAction.HOLD,
            confidence=min(confidence, 0.9),
            key_points=points,
        )


class JudgeAgent:
    agent_id = "judge_agent"

    async def synthesize(
        self,
        ctx: PipelineContext,
        bull: DebateArgument,
        bear: DebateArgument,
    ) -> DebateVerdict:
        # Regime-weighted scoring: in crisis, bear gets 2x weight
        regime_weights = {
            MarketRegime.CRISIS: (0.3, 0.7),
            MarketRegime.HIGH_VOLATILITY: (0.4, 0.6),
            MarketRegime.TRENDING: (0.65, 0.35),
            MarketRegime.MEAN_REVERTING: (0.5, 0.5),
            MarketRegime.UNKNOWN: (0.5, 0.5),
        }
        bull_w, bear_w = regime_weights.get(ctx.regime, (0.5, 0.5))

        bull_score = bull.confidence * bull_w
        bear_score = bear.confidence * bear_w

        if bull_score > bear_score + 0.1:
            action, confidence = TradeAction.BUY, bull_score
        elif bear_score > bull_score + 0.1:
            action = bear.stance if bear.stance != TradeAction.BUY else TradeAction.SELL
            confidence = bear_score
        else:
            action, confidence = TradeAction.HOLD, max(bull_score, bear_score)

        confidence = min(confidence, 1.0)
        if confidence < settings.risk.min_confidence:
            action = TradeAction.HOLD

        return DebateVerdict(
            symbol=ctx.symbol,
            action=action,
            confidence=confidence,
            bull_summary="; ".join(bull.key_points[:3]),
            bear_summary="; ".join(bear.key_points[:3]),
            synthesis=f"Regime={ctx.regime.value}, bull_score={bull_score:.2f}, bear_score={bear_score:.2f}",
        )


class DebateCoordinator:
    agent_id = "debate_coordinator"

    def __init__(self) -> None:
        self.bull = BullAgent()
        self.bear = BearAgent()
        self.judge = JudgeAgent()

    async def run_debate(self, ctx: PipelineContext) -> DebateVerdict:
        bull_arg = await self.bull.argue(ctx)
        bear_arg = await self.bear.argue(ctx)
        # Round 2: agents address counterpoints (advanced debate loop)
        for _ in range(max(0, settings.debate_rounds - 1)):
            bear_arg.counterpoints_addressed = bull_arg.key_points[:2]
            bull_arg.counterpoints_addressed = bear_arg.key_points[:2]
        return await self.judge.synthesize(ctx, bull_arg, bear_arg)
