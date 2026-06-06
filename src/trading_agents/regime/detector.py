from __future__ import annotations

import numpy as np

from trading_agents.config import MarketRegime
from trading_agents.core.blackboard import PipelineContext
from trading_agents.tools.market_data import MarketDataProvider


class RegimeDetector:
    """Classifies market regime from recent price action (rule-based; upgrade to HMM/GMM later)."""

    agent_id = "regime_detector"

    def __init__(self, market_data: MarketDataProvider) -> None:
        self.market_data = market_data

    async def detect(self, ctx: PipelineContext) -> MarketRegime:
        bars = await self.market_data.get_bars(ctx.symbol, limit=60)
        if len(bars) < 20:
            return MarketRegime.UNKNOWN

        closes = np.array([b["close"] for b in bars])
        returns = np.diff(closes) / closes[:-1]
        vol = float(np.std(returns))
        trend = float((closes[-1] - closes[0]) / closes[0])

        if vol > 0.025:
            return MarketRegime.HIGH_VOLATILITY
        if vol > 0.04 or trend < -0.08:
            return MarketRegime.CRISIS
        if abs(trend) > 0.05:
            return MarketRegime.TRENDING
        if vol < 0.008:
            return MarketRegime.MEAN_REVERTING
        return MarketRegime.UNKNOWN
