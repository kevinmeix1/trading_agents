from __future__ import annotations

import structlog

from trading_agents.config import settings
from trading_agents.core.blackboard import Blackboard, PipelineContext
from trading_agents.core.events import Event, EventBus, EventType
from trading_agents.schemas import PipelineResult, TradeAction

log = structlog.get_logger()


class TradingOrchestrator:
    """
    Hierarchical meta-orchestrator.

    Runs the multi-agent pipeline in strict phases:
      regime → analysis (parallel) → debate → portfolio → risk veto → execution

    The risk veto gate is the only phase that can hard-block a trade.
    """

    def __init__(
        self,
        *,
        regime_detector,
        market_analyst,
        sentiment_analyst,
        debate_coordinator,
        portfolio_manager,
        risk_gate,
        execution_agent,
        event_bus: EventBus | None = None,
        blackboard: Blackboard | None = None,
    ) -> None:
        self.regime_detector = regime_detector
        self.market_analyst = market_analyst
        self.sentiment_analyst = sentiment_analyst
        self.debate_coordinator = debate_coordinator
        self.portfolio_manager = portfolio_manager
        self.risk_gate = risk_gate
        self.execution_agent = execution_agent
        self.event_bus = event_bus or EventBus()
        self.blackboard = blackboard or Blackboard()

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        self.event_bus.emit(
            Event(
                type=EventType.PIPELINE_STARTED,
                run_id=ctx.run_id,
                payload={"symbol": ctx.symbol},
            )
        )

        try:
            ctx = await self._phase_regime(ctx)
            ctx = await self._phase_analysis(ctx)
            ctx = await self._phase_debate(ctx)
            ctx = await self._phase_portfolio(ctx)

            if ctx.proposal is None or ctx.proposal.action == TradeAction.HOLD:
                return self._complete(ctx, blocked=False)

            ctx = await self._phase_risk(ctx)
            if ctx.risk and not ctx.risk.approved:
                return self._complete(
                    ctx,
                    blocked=True,
                    block_reason="; ".join(ctx.risk.violations) or "Risk gate rejected",
                )

            ctx = await self._phase_execution(ctx)
            return self._complete(ctx)

        except Exception as exc:
            self.event_bus.emit(
                Event(
                    type=EventType.AGENT_ERROR,
                    run_id=ctx.run_id,
                    payload={"error": str(exc)},
                )
            )
            log.exception("pipeline_failed", run_id=ctx.run_id, symbol=ctx.symbol)
            raise

    async def _phase_regime(self, ctx: PipelineContext) -> PipelineContext:
        ctx.regime = await self.regime_detector.detect(ctx)
        ctx.sync_to_blackboard(self.blackboard)
        self.event_bus.emit(
            Event(
                type=EventType.REGIME_DETECTED,
                run_id=ctx.run_id,
                agent_id=self.regime_detector.agent_id,
                payload={"regime": ctx.regime.value},
            )
        )
        return ctx

    async def _phase_analysis(self, ctx: PipelineContext) -> PipelineContext:
        import asyncio

        market_task = self.market_analyst.analyze(ctx)
        sentiment_task = self.sentiment_analyst.analyze(ctx)
        ctx.market_analysis, ctx.sentiment = await asyncio.gather(market_task, sentiment_task)
        ctx.sync_to_blackboard(self.blackboard)
        self.event_bus.emit(
            Event(
                type=EventType.ANALYSIS_COMPLETE,
                run_id=ctx.run_id,
                payload={
                    "market_direction": ctx.market_analysis.direction.value
                    if ctx.market_analysis
                    else None,
                    "sentiment_score": ctx.sentiment.score if ctx.sentiment else None,
                },
            )
        )
        return ctx

    async def _phase_debate(self, ctx: PipelineContext) -> PipelineContext:
        ctx.debate_verdict = await self.debate_coordinator.run_debate(ctx)
        ctx.sync_to_blackboard(self.blackboard)
        self.event_bus.emit(
            Event(
                type=EventType.DEBATE_COMPLETE,
                run_id=ctx.run_id,
                agent_id=self.debate_coordinator.agent_id,
                payload={"action": ctx.debate_verdict.action.value, "confidence": ctx.debate_verdict.confidence},
            )
        )
        return ctx

    async def _phase_portfolio(self, ctx: PipelineContext) -> PipelineContext:
        ctx.proposal = await self.portfolio_manager.propose(ctx)
        ctx.sync_to_blackboard(self.blackboard)
        if ctx.proposal:
            self.event_bus.emit(
                Event(
                    type=EventType.PROPOSAL_CREATED,
                    run_id=ctx.run_id,
                    agent_id=self.portfolio_manager.agent_id,
                    payload={
                        "action": ctx.proposal.action.value,
                        "quantity": ctx.proposal.quantity,
                    },
                )
            )
        return ctx

    async def _phase_risk(self, ctx: PipelineContext) -> PipelineContext:
        ctx.risk = await self.risk_gate.assess(ctx)
        ctx.sync_to_blackboard(self.blackboard)
        self.event_bus.emit(
            Event(
                type=EventType.RISK_CHECK,
                run_id=ctx.run_id,
                agent_id=self.risk_gate.agent_id,
                payload={"approved": ctx.risk.approved, "violations": ctx.risk.violations},
            )
        )
        if not ctx.risk.approved:
            self.event_bus.emit(
                Event(
                    type=EventType.PIPELINE_BLOCKED,
                    run_id=ctx.run_id,
                    payload={"reason": ctx.risk.violations},
                )
            )
        return ctx

    async def _phase_execution(self, ctx: PipelineContext) -> PipelineContext:
        order = await self.execution_agent.execute(ctx)
        ctx.metadata["order"] = order
        self.event_bus.emit(
            Event(
                type=EventType.ORDER_SUBMITTED,
                run_id=ctx.run_id,
                agent_id=self.execution_agent.agent_id,
                payload={"order_id": order.id, "status": order.status.value},
            )
        )
        if order.status.value == "filled":
            self.event_bus.emit(
                Event(
                    type=EventType.ORDER_FILLED,
                    run_id=ctx.run_id,
                    payload={"fill_price": order.fill_price},
                )
            )
        return ctx

    def _complete(
        self,
        ctx: PipelineContext,
        *,
        blocked: bool = False,
        block_reason: str = "",
    ) -> PipelineResult:
        result = PipelineResult(
            run_id=ctx.run_id,
            symbol=ctx.symbol,
            regime=ctx.regime.value,
            verdict=ctx.debate_verdict,
            proposal=ctx.proposal,
            risk=ctx.risk,
            order=ctx.metadata.get("order"),
            blocked=blocked,
            block_reason=block_reason,
        )
        self.event_bus.emit(
            Event(
                type=EventType.PIPELINE_COMPLETE,
                run_id=ctx.run_id,
                payload={"blocked": blocked, "action": result.proposal.action.value if result.proposal else "hold"},
            )
        )
        return result
