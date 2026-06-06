from __future__ import annotations

from abc import ABC, abstractmethod

from trading_agents.core.blackboard import PipelineContext


class BaseAgent(ABC):
    agent_id: str = "base"

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ...
