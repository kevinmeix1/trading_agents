"""Typed outputs shared across agents.

Using ``pydantic`` models gives us validation, clamping and JSON serialisation
for free, and documents the contract between agents in the pipeline.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class AnalystReport(BaseModel):
    """Output of a single analyst agent."""

    agent: str
    # -1.0 (max bearish) .. +1.0 (max bullish)
    signal: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    key_points: list[str] = Field(default_factory=list)

    @property
    def stance(self) -> str:
        if self.signal > 0.2:
            return "bullish"
        if self.signal < -0.2:
            return "bearish"
        return "neutral"


class DebateResult(BaseModel):
    """Outcome of the bull-vs-bear research debate."""

    bull_thesis: str
    bear_thesis: str
    rounds: int
    judge_summary: str
    # Net conviction after the debate, -1.0 .. +1.0
    conviction: float = Field(ge=-1.0, le=1.0)


class RiskAssessment(BaseModel):
    """Risk officer's verdict and sizing guardrails."""

    approved: bool
    position_size_pct: float = Field(ge=0.0, le=1.0)
    stop_loss_pct: float = Field(ge=0.0, le=1.0)
    take_profit_pct: float = Field(ge=0.0, le=2.0)
    rationale: str
    flags: list[str] = Field(default_factory=list)


class TradeDecision(BaseModel):
    """Final, actionable decision from the portfolio manager."""

    symbol: str
    action: Action
    # Fraction of portfolio equity to allocate to this position (0..1).
    target_weight: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    stop_loss_pct: float = Field(ge=0.0, le=1.0, default=0.0)
    take_profit_pct: float = Field(ge=0.0, le=2.0, default=0.0)
    rationale: str = ""
