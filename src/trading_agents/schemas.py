from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    volume: float
    bid: float | None = None
    ask: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketAnalysis(BaseModel):
    symbol: str
    direction: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    support_level: float | None = None
    resistance_level: float | None = None
    indicators: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""


class SentimentReport(BaseModel):
    symbol: str
    score: float = Field(ge=-1.0, le=1.0, description="-1 bearish, +1 bullish")
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    summary: str = ""


class DebateArgument(BaseModel):
    agent_id: str
    stance: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: list[str] = Field(default_factory=list)
    counterpoints_addressed: list[str] = Field(default_factory=list)


class DebateVerdict(BaseModel):
    symbol: str
    action: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    bull_summary: str = ""
    bear_summary: str = ""
    synthesis: str = ""


class TradeProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    action: TradeAction
    quantity: float
    limit_price: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAssessment(BaseModel):
    approved: bool
    violations: list[str] = Field(default_factory=list)
    adjusted_quantity: float | None = None
    notes: str = ""


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    proposal_id: str
    symbol: str
    side: TradeAction
    quantity: float
    limit_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioState(BaseModel):
    cash: float = 100_000.0
    positions: dict[str, float] = Field(default_factory=dict)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    orders_today: int = 0


class PipelineResult(BaseModel):
    run_id: str
    symbol: str
    regime: str
    verdict: DebateVerdict | None = None
    proposal: TradeProposal | None = None
    risk: RiskAssessment | None = None
    order: Order | None = None
    blocked: bool = False
    block_reason: str = ""
