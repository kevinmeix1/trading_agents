"""A deterministic, dependency-free "LLM".

The offline model never makes a network call. For :meth:`structured` it simply
trusts the heuristic ``fallback`` the agent already computed, which means the
entire multi-agent pipeline runs and is fully reproducible without any API key.

For :meth:`chat` (used by the free-form debate) it produces a deterministic,
grounded summary of the numeric facts it can find in the prompt so the output is
still readable rather than random.
"""

from __future__ import annotations

import re
from typing import Any

from trading_agents.llm.base import ChatModel, Message


class OfflineChatModel(ChatModel):
    name = "offline-heuristic"

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        system = next((m.content for m in messages if m.role == "system"), "")

        # Pull out any "key: value" numeric facts to ground the reply.
        facts = re.findall(r"([A-Za-z_][\w ]*?):\s*(-?\d+(?:\.\d+)?%?)", user)
        fact_str = "; ".join(f"{k.strip()}={v}" for k, v in facts[:6])

        persona = "analyst"
        low = system.lower()
        if "bull" in low:
            persona = "bull"
        elif "bear" in low:
            persona = "bear"
        elif "risk" in low:
            persona = "risk officer"

        lead = {
            "bull": "The constructive case is supported by",
            "bear": "The cautionary case is supported by",
            "risk officer": "From a risk standpoint, the relevant figures are",
            "analyst": "Key observations:",
        }[persona]

        body = fact_str if fact_str else "the supplied context"
        return f"[offline:{persona}] {lead} {body}."

    def structured(
        self,
        *,
        system: str,
        user: str,
        fallback: dict[str, Any],
        temperature: float | None = None,
    ) -> dict[str, Any]:
        # The heuristic fallback IS the decision in offline mode.
        return dict(fallback)
