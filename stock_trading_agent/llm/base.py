"""Base types for the LLM abstraction layer."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    """A single chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


def extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object embedded in ``text``.

    Handles models that wrap JSON in prose or in ```json fences.
    """

    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1))

    # Greedy outermost-brace match as a fallback.
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


class ChatModel(ABC):
    """Abstract chat model.

    Concrete implementations must provide :meth:`chat`. The :meth:`structured`
    helper is shared and turns a free-form completion into a dict, gracefully
    falling back to a supplied heuristic when parsing fails or the call errors.
    """

    name: str = "chat-model"

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return a completion string for ``messages``."""

    def structured(
        self,
        *,
        system: str,
        user: str,
        fallback: dict[str, Any],
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object decision.

        ``fallback`` is a fully-formed heuristic decision. It is used verbatim
        when the model is offline, errors out, or returns unparseable text. When
        the model does return valid JSON, missing keys are back-filled from the
        fallback so downstream code always sees a complete object.
        """

        messages = [
            Message("system", system),
            Message(
                "user",
                user
                + "\n\nRespond with ONLY a single JSON object matching the keys: "
                + ", ".join(fallback.keys())
                + ".",
            ),
        ]
        try:
            raw = self.chat(messages, temperature=temperature)
        except Exception:
            return dict(fallback)

        parsed = extract_json(raw)
        if not parsed:
            return dict(fallback)

        merged = dict(fallback)
        merged.update({k: v for k, v in parsed.items() if v is not None})
        return merged
