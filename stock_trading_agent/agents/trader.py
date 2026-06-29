"""Portfolio manager: the final decision maker.

Combines the debate conviction with the risk officer's guardrails into a single
actionable :class:`~stock_trading_agent.agents.schemas.TradeDecision`.
"""

from __future__ import annotations

from typing import Any

from stock_trading_agent.agents.base import AgentContext, BaseAgent
from stock_trading_agent.agents.schemas import Action, DebateResult, RiskAssessment, TradeDecision


class PortfolioManager(BaseAgent):
    role = "portfolio_manager"

    def __init__(self, llm, settings, *, action_threshold: float = 0.15):
        super().__init__(llm, settings)
        self.action_threshold = action_threshold

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        debate: DebateResult | None = ctx.scratchpad.get("debate")
        risk: RiskAssessment | None = ctx.scratchpad.get("risk")
        conviction = debate.conviction if debate else 0.0

        if not risk or not risk.approved:
            action = Action.HOLD
            weight = 0.0
            reason = "Risk did not approve a position." if risk else "No risk assessment."
        elif conviction >= self.action_threshold:
            action = Action.BUY
            weight = risk.position_size_pct
            reason = "Bullish conviction cleared risk checks."
        elif conviction <= -self.action_threshold:
            action = Action.SELL
            weight = risk.position_size_pct
            reason = "Bearish conviction cleared risk checks."
        else:
            action = Action.HOLD
            weight = 0.0
            reason = "Conviction inside neutral band."

        confidence = min(1.0, abs(conviction) + 0.1)
        rationale = (
            f"{reason} Conviction {conviction:+.2f}; target weight {weight:.2%}. "
            + (debate.judge_summary if debate else "")
        )
        return {
            "symbol": ctx.symbol,
            "action": action.value,
            "target_weight": round(weight, 4),
            "confidence": round(confidence, 4),
            "stop_loss_pct": risk.stop_loss_pct if risk else 0.0,
            "take_profit_pct": risk.take_profit_pct if risk else 0.0,
            "rationale": rationale,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        debate: DebateResult | None = ctx.scratchpad.get("debate")
        risk: RiskAssessment | None = ctx.scratchpad.get("risk")
        system = (
            "You are the portfolio manager with final authority. Combine conviction "
            "and the risk mandate into one decision. You MUST respect risk approval "
            "and sizing. Output keys: symbol, action (BUY/SELL/HOLD), target_weight, "
            "confidence, stop_loss_pct, take_profit_pct, rationale."
        )
        user = (
            f"Symbol: {ctx.symbol}\n"
            f"conviction: {debate.conviction if debate else 0.0}\n"
            f"risk_approved: {risk.approved if risk else False}\n"
            f"risk_size: {risk.position_size_pct if risk else 0.0}\n"
            f"action_threshold: {self.action_threshold}"
        )
        return system, user

    def decide(self, ctx: AgentContext) -> TradeDecision:
        data = self.reason(ctx)
        action = data["action"]
        if isinstance(action, str):
            action = Action(action.upper())
        decision = TradeDecision(
            symbol=ctx.symbol,
            action=action,
            target_weight=max(0.0, min(1.0, float(data["target_weight"]))),
            confidence=max(0.0, min(1.0, float(data["confidence"]))),
            stop_loss_pct=max(0.0, min(1.0, float(data.get("stop_loss_pct", 0.0)))),
            take_profit_pct=max(0.0, min(2.0, float(data.get("take_profit_pct", 0.0)))),
            rationale=str(data.get("rationale", "")),
        )
        ctx.remember("decision", decision)
        self.log(f"DECISION {decision.action.value} weight={decision.target_weight:.2%}")
        return decision
