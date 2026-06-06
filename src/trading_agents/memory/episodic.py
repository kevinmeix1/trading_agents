from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from trading_agents.schemas import PipelineResult


class TradeEpisode(BaseModel):
    run_id: str
    symbol: str
    action: str
    outcome_pnl: float | None = None
    verdict_summary: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EpisodicMemory:
    """Stores past pipeline runs for agent context and future RL training."""

    def __init__(self, max_episodes: int = 500) -> None:
        self._episodes: list[TradeEpisode] = []
        self.max_episodes = max_episodes

    def record(self, result: PipelineResult) -> None:
        episode = TradeEpisode(
            run_id=result.run_id,
            symbol=result.symbol,
            action=result.proposal.action.value if result.proposal else "hold",
            verdict_summary=result.verdict.synthesis if result.verdict else "",
        )
        self._episodes.append(episode)
        if len(self._episodes) > self.max_episodes:
            self._episodes = self._episodes[-self.max_episodes :]

    def recent(self, symbol: str | None = None, limit: int = 10) -> list[TradeEpisode]:
        episodes = self._episodes
        if symbol:
            episodes = [e for e in episodes if e.symbol == symbol]
        return episodes[-limit:]

    def win_rate(self, symbol: str | None = None) -> float | None:
        episodes = self.recent(symbol, limit=100)
        with_outcome = [e for e in episodes if e.outcome_pnl is not None]
        if not with_outcome:
            return None
        wins = sum(1 for e in with_outcome if e.outcome_pnl > 0)
        return wins / len(with_outcome)
