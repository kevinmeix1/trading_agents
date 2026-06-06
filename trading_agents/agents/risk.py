"""Risk management agent.

Translates a research conviction into prudent sizing and guardrails using
volatility targeting, then approves or vetoes the trade against hard limits.
"""

from __future__ import annotations

from typing import Any

from trading_agents.agents.base import AgentContext, BaseAgent
from trading_agents.agents.schemas import DebateResult, RiskAssessment


class RiskManager(BaseAgent):
    role = "risk_manager"

    def __init__(
        self,
        llm,
        settings,
        *,
        target_volatility: float = 0.20,
        max_position: float = 0.30,
        max_asset_vol: float = 0.80,
        min_conviction: float = 0.10,
    ):
        super().__init__(llm, settings)
        self.target_volatility = target_volatility
        self.max_position = max_position
        self.max_asset_vol = max_asset_vol
        self.min_conviction = min_conviction

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        debate: DebateResult | None = ctx.scratchpad.get("debate")
        conviction = debate.conviction if debate else 0.0
        vol = max(ctx.indicators.annualised_vol, 1e-6)

        flags: list[str] = []

        # Volatility-targeted base size, scaled by conviction strength.
        vol_scalar = min(1.0, self.target_volatility / vol)
        base_size = vol_scalar * abs(conviction)
        position = min(self.max_position, base_size)

        approved = True
        if abs(conviction) < self.min_conviction:
            approved = False
            flags.append("Conviction below minimum threshold.")
        if vol > self.max_asset_vol:
            approved = False
            position = 0.0
            flags.append(f"Asset volatility {vol:.2f} exceeds limit {self.max_asset_vol}.")
        if ctx.memory_notes:
            flags.append("Reviewed prior-trade reflections.")

        # Stops scale with volatility (wider stops in choppier names).
        stop_loss = min(0.25, max(0.03, vol * 0.5))
        take_profit = min(0.60, stop_loss * 2.0)

        rationale = (
            f"Vol-target sizing: asset vol {vol:.2f} vs target {self.target_volatility:.2f} "
            f"=> scalar {vol_scalar:.2f}; conviction {conviction:+.2f} => size {position:.2%}. "
            f"Stop {stop_loss:.0%}, target {take_profit:.0%}."
        )
        return {
            "approved": approved,
            "position_size_pct": round(position, 4),
            "stop_loss_pct": round(stop_loss, 4),
            "take_profit_pct": round(take_profit, 4),
            "rationale": rationale,
            "flags": flags,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        debate: DebateResult | None = ctx.scratchpad.get("debate")
        system = (
            "You are a conservative risk manager. Given conviction and volatility, "
            "decide approval and sizing. Never exceed the max position. Output keys: "
            "approved (bool), position_size_pct, stop_loss_pct, take_profit_pct, "
            "rationale, flags (list)."
        )
        user = (
            f"Symbol: {ctx.symbol}\n"
            f"conviction: {debate.conviction if debate else 0.0}\n"
            f"annualised_vol: {ctx.indicators.annualised_vol}\n"
            f"target_volatility: {self.target_volatility}\n"
            f"max_position: {self.max_position}"
        )
        return system, user

    def assess(self, ctx: AgentContext) -> RiskAssessment:
        data = self.reason(ctx)
        assessment = RiskAssessment(
            approved=bool(data["approved"]),
            position_size_pct=max(0.0, min(self.max_position, float(data["position_size_pct"]))),
            stop_loss_pct=max(0.0, min(1.0, float(data["stop_loss_pct"]))),
            take_profit_pct=max(0.0, min(2.0, float(data["take_profit_pct"]))),
            rationale=str(data["rationale"]),
            flags=list(data.get("flags", [])),
        )
        ctx.remember("risk", assessment)
        self.log(
            f"approved={assessment.approved} size={assessment.position_size_pct:.2%} "
            f"stop={assessment.stop_loss_pct:.0%}"
        )
        return assessment
