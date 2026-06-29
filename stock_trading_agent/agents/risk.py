"""Risk management agent.

Translates a research conviction into prudent sizing and guardrails using
volatility targeting, then approves or vetoes the trade against hard limits.
"""

from __future__ import annotations

from typing import Any

from stock_trading_agent.agents.base import AgentContext, BaseAgent
from stock_trading_agent.agents.schemas import DebateResult, RiskAssessment


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
        kelly_fraction: float = 0.5,
        max_drawdown_guard: float = 0.25,
    ):
        super().__init__(llm, settings)
        self.target_volatility = target_volatility
        self.max_position = max_position
        self.max_asset_vol = max_asset_vol
        self.min_conviction = min_conviction
        self.kelly_fraction = max(0.0, min(1.0, kelly_fraction))
        self.max_drawdown_guard = max_drawdown_guard

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        debate: DebateResult | None = ctx.scratchpad.get("debate")
        conviction = debate.conviction if debate else 0.0
        ind = ctx.indicators
        vol = max(ind.annualised_vol, 1e-6)

        flags: list[str] = []

        # (1) Volatility-targeted base size, scaled by conviction strength.
        vol_scalar = min(1.0, self.target_volatility / vol)
        vol_target_size = vol_scalar * abs(conviction)

        # (2) Fractional-Kelly size. Treat conviction as an expected excess
        # return of ``|conviction| * target_volatility`` against a variance of
        # ``vol**2``; full Kelly is mu / sigma**2. We then scale by the
        # configured Kelly fraction to temper the notoriously aggressive bet.
        kelly_full = min(1.0, abs(conviction) * self.target_volatility / (vol**2))
        blended = (1.0 - self.kelly_fraction) * vol_target_size + self.kelly_fraction * kelly_full
        position = min(self.max_position, blended)

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

        # Adaptive stops: prefer ATR (true range) when available, else fall back
        # to annualised volatility. Choppier names automatically get wider stops.
        atr_pct = getattr(ind, "atr_pct", 0.0) or 0.0
        stop_basis = atr_pct * 2.5 if atr_pct > 0 else vol * 0.5
        stop_loss = min(0.25, max(0.03, stop_basis))
        take_profit = min(0.60, stop_loss * 2.0)

        rationale = (
            f"Sizing blend (kelly {self.kelly_fraction:.0%}): vol-target {vol_target_size:.2%}, "
            f"frac-Kelly {self.kelly_fraction * kelly_full:.2%} => {position:.2%}. "
            f"Asset vol {vol:.2f} vs target {self.target_volatility:.2f}; "
            f"ATR stop {stop_loss:.0%}, target {take_profit:.0%}."
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
