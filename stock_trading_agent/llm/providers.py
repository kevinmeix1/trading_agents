"""Concrete LLM providers (OpenAI and Anthropic).

These are imported lazily so the package works without the optional SDKs
installed. They share the :class:`ChatModel` interface, so swapping providers is
purely a configuration change.
"""

from __future__ import annotations

from stock_trading_agent.llm.base import ChatModel, Message


class OpenAIChatModel(ChatModel):
    def __init__(self, model: str, api_key: str | None, temperature: float, max_tokens: int):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "openai is not installed. `pip install stock-trading-agent[openai]` "
                "or set STA_LLM_PROVIDER=offline."
            ) from exc
        self._client = OpenAI(api_key=api_key)
        self.name = f"openai:{model}"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[m.as_dict() for m in messages],
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
        )
        return resp.choices[0].message.content or ""


class AnthropicChatModel(ChatModel):
    def __init__(self, model: str, api_key: str | None, temperature: float, max_tokens: int):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                "anthropic is not installed. `pip install stock-trading-agent[anthropic]` "
                "or set STA_LLM_PROVIDER=offline."
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self.name = f"anthropic:{model}"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        system = "\n".join(m.content for m in messages if m.role == "system")
        convo = [m.as_dict() for m in messages if m.role != "system"]
        resp = self._client.messages.create(
            model=self.model,
            system=system or None,
            messages=convo,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
        )
        parts = [block.text for block in resp.content if getattr(block, "type", None) == "text"]
        return "".join(parts)
