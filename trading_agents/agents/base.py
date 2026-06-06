"""Base agent abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from trading_agents.config import Settings
from trading_agents.data.indicators import IndicatorSnapshot
from trading_agents.data.types import PriceHistory
from trading_agents.llm.base import ChatModel

_console = Console()


@dataclass
class AgentContext:
    """Everything an agent needs to reason about one decision.

    The context is threaded through the whole pipeline. Earlier agents write
    their conclusions into ``scratchpad`` so later agents can read them, which is
    how the analysts inform the debate, the debate informs risk, and so on.
    """

    symbol: str
    history: PriceHistory
    indicators: IndicatorSnapshot
    settings: Settings
    # Free-form shared state between agents (analyst reports, debate, etc.).
    scratchpad: dict[str, Any] = field(default_factory=dict)
    # Optional context surfaced from reflection memory.
    memory_notes: list[str] = field(default_factory=list)
    # Optional headline/news strings for the sentiment analyst.
    news: list[str] = field(default_factory=list)

    def remember(self, key: str, value: Any) -> None:
        self.scratchpad[key] = value


class BaseAgent(ABC):
    """Common machinery for every reasoning agent.

    Sub-classes implement :meth:`heuristic` (a rule-based decision computed from
    data) and :meth:`prompt` (the system/user prompt for an LLM). The base class
    handles the LLM round-trip and offline fallback uniformly.
    """

    role: str = "agent"

    def __init__(self, llm: ChatModel, settings: Settings):
        self.llm = llm
        self.settings = settings

    # -- to be implemented by subclasses ------------------------------------
    @abstractmethod
    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        """Return a complete decision dict from deterministic rules."""

    @abstractmethod
    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        """Return ``(system_prompt, user_prompt)`` for the LLM."""

    # -- shared logic -------------------------------------------------------
    def reason(self, ctx: AgentContext) -> dict[str, Any]:
        """Produce a decision dict, using the LLM when available."""

        fallback = self.heuristic(ctx)
        system, user = self.prompt(ctx)
        result = self.llm.structured(
            system=system,
            user=user,
            fallback=fallback,
            temperature=self.settings.llm_temperature,
        )
        return result

    def log(self, message: str) -> None:
        if self.settings.verbose:
            _console.print(f"[dim]│[/dim] [bold cyan]{self.role}[/bold cyan] {message}")
