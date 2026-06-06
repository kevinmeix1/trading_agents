from __future__ import annotations

from trading_agents.core.blackboard import PipelineContext
from trading_agents.schemas import SentimentReport


class SentimentAnalyst:
    """Mock sentiment agent — replace with news API + LLM summarization in Phase 2."""

    agent_id = "sentiment_analyst"

    async def analyze(self, ctx: PipelineContext) -> SentimentReport:
        # Deterministic mock based on symbol hash for reproducible demos
        seed = sum(ord(c) for c in ctx.symbol) % 100
        score = (seed - 50) / 50.0  # -1 to +1
        confidence = 0.5 + (seed % 30) / 100.0

        bias = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
        return SentimentReport(
            symbol=ctx.symbol,
            score=score,
            confidence=min(confidence, 0.8),
            sources=["mock_news_feed", "mock_social_aggregate"],
            summary=f"Mock sentiment for {ctx.symbol}: {bias} (score={score:.2f})",
        )
