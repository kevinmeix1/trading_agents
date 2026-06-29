"""Provider-agnostic LLM access.

The :class:`ChatModel` interface hides the differences between OpenAI,
Anthropic and a fully offline deterministic backend. Agents only ever talk to
this interface, which keeps the rest of the system testable without API keys.
"""

from stock_trading_agent.llm.base import ChatModel, Message
from stock_trading_agent.llm.factory import get_chat_model
from stock_trading_agent.llm.offline import OfflineChatModel

__all__ = ["ChatModel", "Message", "OfflineChatModel", "get_chat_model"]
