"""Factory that builds the configured :class:`ChatModel`."""

from __future__ import annotations

from stock_trading_agent.config import LLMProvider, Settings, get_settings
from stock_trading_agent.llm.base import ChatModel
from stock_trading_agent.llm.offline import OfflineChatModel


def get_chat_model(settings: Settings | None = None) -> ChatModel:
    """Return a chat model based on ``settings.llm_provider``.

    Falls back to the offline model if a live provider is selected but its API
    key is missing, so misconfiguration degrades gracefully instead of crashing.
    """

    settings = settings or get_settings()

    if settings.llm_provider == LLMProvider.OPENAI:
        if not settings.openai_api_key:
            return OfflineChatModel()
        from stock_trading_agent.llm.providers import OpenAIChatModel

        return OpenAIChatModel(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if settings.llm_provider == LLMProvider.ANTHROPIC:
        if not settings.anthropic_api_key:
            return OfflineChatModel()
        from stock_trading_agent.llm.providers import AnthropicChatModel

        return AnthropicChatModel(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    return OfflineChatModel()
