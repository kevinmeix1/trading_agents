from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from trading_agents.config import MarketRegime
from trading_agents.schemas import (
    DebateVerdict,
    MarketAnalysis,
    MarketSnapshot,
    PortfolioState,
    RiskAssessment,
    SentimentReport,
    TradeProposal,
)


class BlackboardEntry(BaseModel):
    key: str
    value: Any
    agent_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Blackboard:
    """
    Shared knowledge surface for agents (Blackboard pattern).

    Agents publish structured artifacts here instead of passing long chat
    histories. The orchestrator reads the blackboard between pipeline phases.
    """

    def __init__(self) -> None:
        self._store: dict[str, BlackboardEntry] = {}
        self._history: list[BlackboardEntry] = []

    def write(self, key: str, value: Any, agent_id: str) -> None:
        entry = BlackboardEntry(key=key, value=value, agent_id=agent_id)
        self._store[key] = entry
        self._history.append(entry)

    def read(self, key: str, default: Any = None) -> Any:
        entry = self._store.get(key)
        return entry.value if entry else default

    def read_entry(self, key: str) -> BlackboardEntry | None:
        return self._store.get(key)

    def keys(self) -> list[str]:
        return list(self._store.keys())

    @property
    def history(self) -> list[BlackboardEntry]:
        return list(self._history)


class PipelineContext(BaseModel):
    """Working memory for a single pipeline run."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    regime: MarketRegime = MarketRegime.UNKNOWN
    snapshot: MarketSnapshot | None = None
    market_analysis: MarketAnalysis | None = None
    sentiment: SentimentReport | None = None
    debate_verdict: DebateVerdict | None = None
    proposal: TradeProposal | None = None
    risk: RiskAssessment | None = None
    portfolio: PortfolioState = Field(default_factory=PortfolioState)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def sync_to_blackboard(self, blackboard: Blackboard, agent_id: str = "orchestrator") -> None:
        if self.snapshot:
            blackboard.write("snapshot", self.snapshot, agent_id)
        if self.market_analysis:
            blackboard.write("market_analysis", self.market_analysis, agent_id)
        if self.sentiment:
            blackboard.write("sentiment", self.sentiment, agent_id)
        if self.debate_verdict:
            blackboard.write("debate_verdict", self.debate_verdict, agent_id)
        if self.proposal:
            blackboard.write("proposal", self.proposal, agent_id)
        if self.risk:
            blackboard.write("risk", self.risk, agent_id)
        blackboard.write("regime", self.regime, agent_id)
        blackboard.write("portfolio", self.portfolio, agent_id)
