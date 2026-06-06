from __future__ import annotations

from trading_agents.core.blackboard import PipelineContext
from trading_agents.schemas import TradeAction, TradeProposal


class PortfolioManager:
    agent_id = "portfolio_manager"

    async def propose(self, ctx: PipelineContext) -> TradeProposal | None:
        if not ctx.debate_verdict:
            return None

        verdict = ctx.debate_verdict
        if verdict.action == TradeAction.HOLD:
            return TradeProposal(
                symbol=ctx.symbol,
                action=TradeAction.HOLD,
                quantity=0,
                confidence=verdict.confidence,
                rationale=verdict.synthesis,
            )

        price = ctx.snapshot.price if ctx.snapshot else 100.0
        portfolio_value = ctx.portfolio.cash + sum(
            abs(q) * price for q in ctx.portfolio.positions.values()
        )
        # Kelly-inspired fractional sizing capped at 5% of portfolio
        base_pct = 0.02 + (verdict.confidence - 0.5) * 0.06
        target_value = portfolio_value * min(base_pct, 0.05)
        quantity = round(target_value / price, 2)

        if quantity <= 0:
            return TradeProposal(
                symbol=ctx.symbol,
                action=TradeAction.HOLD,
                quantity=0,
                confidence=verdict.confidence,
                rationale="Position size below minimum threshold",
            )

        return TradeProposal(
            symbol=ctx.symbol,
            action=verdict.action,
            quantity=quantity,
            limit_price=price,
            confidence=verdict.confidence,
            rationale=f"{verdict.synthesis}; sized at {base_pct:.1%} of portfolio",
        )
