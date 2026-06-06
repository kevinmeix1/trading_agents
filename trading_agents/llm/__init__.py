"""Provider-agnostic LLM access.

The :class:`ChatModel` interface hides the differences between OpenAI,
Anthropic and a fully offline deterministic backend. Agents only ever talk to
this interface, which keeps the rest of the system testable without API keys.
"""

from trading_agents.llm.base import ChatModel, Message
from trading_agents.llm.factory import get_chat_model
from trading_agents.llm.offline import OfflineChatModel

__all__ = ["ChatModel", "Message", "OfflineChatModel", "get_chat_model"]
