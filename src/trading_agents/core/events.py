from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PIPELINE_STARTED = "pipeline.started"
    REGIME_DETECTED = "regime.detected"
    ANALYSIS_COMPLETE = "analysis.complete"
    DEBATE_COMPLETE = "debate.complete"
    PROPOSAL_CREATED = "proposal.created"
    RISK_CHECK = "risk.check"
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    PIPELINE_BLOCKED = "pipeline.blocked"
    PIPELINE_COMPLETE = "pipeline.complete"
    AGENT_ERROR = "agent.error"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    run_id: str
    agent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """In-process event bus for audit trail and future replay/backtesting."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._subscribers: list[Callable[[Event], None]] = []

    def emit(self, event: Event) -> None:
        self._events.append(event)
        for handler in self._subscribers:
            handler(event)

    def subscribe(self, handler: Callable[[Event], None]) -> None:
        self._subscribers.append(handler)

    def history(self, run_id: str | None = None) -> list[Event]:
        if run_id is None:
            return list(self._events)
        return [e for e in self._events if e.run_id == run_id]

    def clear(self) -> None:
        self._events.clear()
