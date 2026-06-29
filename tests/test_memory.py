from __future__ import annotations

from stock_trading_agent.memory.store import MemoryRecord, ReflectionMemory


def test_record_and_recall(tmp_path):
    mem = ReflectionMemory(tmp_path / "mem.json")
    mem.record_decision(
        symbol="AAPL", action="BUY", conviction=0.4, rationale="bullish", realised_return=0.05
    )
    notes = mem.recall("AAPL")
    assert len(notes) == 1
    assert "worked" in notes[0]


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "mem.json"
    mem = ReflectionMemory(path)
    mem.record_decision(symbol="MSFT", action="SELL", conviction=-0.3, rationale="bearish")
    reopened = ReflectionMemory(path)
    assert len(reopened) == 1


def test_hit_rate(tmp_path):
    mem = ReflectionMemory(tmp_path / "mem.json")
    mem.record_decision(symbol="X", action="BUY", conviction=0.2, rationale="", realised_return=0.1)
    mem.record_decision(
        symbol="X", action="BUY", conviction=0.2, rationale="", realised_return=-0.1
    )
    assert mem.hit_rate("X") == 0.5


def test_was_correct_logic():
    win = MemoryRecord(
        symbol="X", timestamp="t", action="BUY", conviction=0.5, rationale="", realised_return=0.1
    )
    loss = MemoryRecord(
        symbol="X", timestamp="t", action="SELL", conviction=-0.5, rationale="", realised_return=0.1
    )
    pending = MemoryRecord(symbol="X", timestamp="t", action="HOLD", conviction=0.0, rationale="")
    assert win.was_correct is True
    assert loss.was_correct is False
    assert pending.was_correct is None
