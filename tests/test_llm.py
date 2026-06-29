from __future__ import annotations

from stock_trading_agent.config import LLMProvider, Settings
from stock_trading_agent.llm.base import Message, extract_json
from stock_trading_agent.llm.factory import get_chat_model
from stock_trading_agent.llm.offline import OfflineChatModel


def test_extract_json_plain():
    assert extract_json('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_extract_json_fenced_with_prose():
    text = "Sure!\n```json\n{\"action\": \"BUY\"}\n```\nHope that helps."
    assert extract_json(text) == {"action": "BUY"}


def test_extract_json_none_on_garbage():
    assert extract_json("no json here") is None


def test_offline_structured_returns_fallback():
    model = OfflineChatModel()
    fallback = {"signal": 0.5, "confidence": 0.8}
    out = model.structured(system="s", user="u", fallback=fallback)
    assert out == fallback


def test_offline_chat_is_grounded():
    model = OfflineChatModel()
    msg = [Message("system", "You are the BULL researcher"), Message("user", "rsi: 65")]
    reply = model.chat(msg)
    assert "bull" in reply.lower()
    assert "rsi" in reply.lower()


def test_factory_falls_back_to_offline_without_keys():
    s = Settings(llm_provider=LLMProvider.OPENAI, openai_api_key=None)
    assert isinstance(get_chat_model(s), OfflineChatModel)


def test_structured_backfills_missing_keys():
    class Echo(OfflineChatModel):
        def chat(self, messages, *, temperature=None, max_tokens=None):
            return '{"signal": 0.9}'

        def structured(self, *, system, user, fallback, temperature=None):
            # Use the base-class implementation to exercise JSON parsing/merge.
            from stock_trading_agent.llm.base import ChatModel

            return ChatModel.structured(
                self, system=system, user=user, fallback=fallback, temperature=temperature
            )

    out = Echo().structured(
        system="s", user="u", fallback={"signal": 0.0, "confidence": 0.5, "rationale": "x"}
    )
    assert out["signal"] == 0.9
    assert out["confidence"] == 0.5  # back-filled
    assert out["rationale"] == "x"
