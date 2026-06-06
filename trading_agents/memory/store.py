"""A lightweight, file-backed reflection memory.

After a trade resolves we store what we decided, why, and how it turned out.
Before the next decision on the same symbol we *recall* the most relevant past
episodes and distil short "lessons" that are injected into agent context. This
is a simple, transparent stand-in for a vector store and works fully offline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class MemoryRecord:
    """One resolved decision and its outcome."""

    symbol: str
    timestamp: str
    action: str
    conviction: float
    rationale: str
    # Realised forward return after the decision (if known).
    realised_return: float | None = None
    lesson: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def was_correct(self) -> bool | None:
        if self.realised_return is None:
            return None
        if self.action == "BUY":
            return self.realised_return > 0
        if self.action == "SELL":
            return self.realised_return < 0
        return abs(self.realised_return) < 0.02


class ReflectionMemory:
    """JSON-backed episodic memory keyed by symbol."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._records: list[MemoryRecord] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text() or "[]")
            self._records = [MemoryRecord(**r) for r in raw]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(r) for r in self._records], indent=2))

    def add(self, record: MemoryRecord) -> None:
        self._records.append(record)
        self._save()

    def record_decision(
        self,
        *,
        symbol: str,
        action: str,
        conviction: float,
        rationale: str,
        realised_return: float | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            symbol=symbol.upper(),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            action=action,
            conviction=conviction,
            rationale=rationale,
            realised_return=realised_return,
            tags=tags or [],
        )
        record.lesson = self._derive_lesson(record)
        self.add(record)
        return record

    @staticmethod
    def _derive_lesson(record: MemoryRecord) -> str:
        correct = record.was_correct
        if correct is None:
            return "Outcome pending."
        if correct:
            return (
                f"{record.action} on {record.symbol} worked "
                f"(ret {record.realised_return:+.2%}); the thesis held."
            )
        return (
            f"{record.action} on {record.symbol} misfired "
            f"(ret {record.realised_return:+.2%}); re-examine the conviction drivers."
        )

    def recall(self, symbol: str, limit: int = 3) -> list[str]:
        """Return recent lesson notes for ``symbol`` (most recent first)."""

        symbol = symbol.upper()
        relevant = [r for r in self._records if r.symbol == symbol and r.lesson]
        relevant.sort(key=lambda r: r.timestamp, reverse=True)
        return [r.lesson for r in relevant[:limit]]

    def hit_rate(self, symbol: str | None = None) -> float | None:
        """Fraction of resolved decisions that were correct."""

        records = [
            r
            for r in self._records
            if r.was_correct is not None and (symbol is None or r.symbol == symbol.upper())
        ]
        if not records:
            return None
        return sum(1 for r in records if r.was_correct) / len(records)

    def __len__(self) -> int:
        return len(self._records)
