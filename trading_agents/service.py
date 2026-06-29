"""Application service layer.

A thin, framework-agnostic facade over the trading pipeline and backtester that
returns plain, JSON-serialisable dictionaries. Both the CLI and the HTTP API are
built on top of this layer, so business logic lives in exactly one place and the
transport (terminal vs. web) stays a thin shell.
"""

from __future__ import annotations

from typing import Any

from trading_agents.agents.schemas import TradeDecision
from trading_agents.backtest import (
    BASELINE_STRATEGIES,
    AgentStrategy,
    Backtester,
    BacktestResult,
)
from trading_agents.config import LLMProvider, Settings, get_settings
from trading_agents.data.market import get_market_provider
from trading_agents.orchestration import TradingPipeline


def _sample_curve(curve, max_points: int = 240) -> list[dict[str, Any]]:
    """Down-sample an equity curve to at most ``max_points`` ``{date, value}``."""

    n = len(curve)
    if n == 0:
        return []
    step = max(1, n // max_points)
    points = []
    for i in range(0, n, step):
        ts = curve.index[i]
        points.append({"date": str(ts.date()), "value": round(float(curve.iloc[i]), 2)})
    # Always include the final point so the line ends on the true last value.
    last_ts = curve.index[-1]
    if not points or points[-1]["date"] != str(last_ts.date()):
        points.append({"date": str(last_ts.date()), "value": round(float(curve.iloc[-1]), 2)})
    return points


class TradingService:
    """High-level operations used by the CLI and the web API."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    # -- introspection ------------------------------------------------------
    def config(self) -> dict[str, Any]:
        s = self.settings
        from trading_agents import __version__

        return {
            "version": __version__,
            "llm_provider": s.llm_provider.value,
            "llm_model": s.llm_model,
            "data_source": s.data_source.value,
            "max_workers": s.max_workers,
            "target_volatility": s.target_volatility,
            "max_position": s.max_position,
            "kelly_fraction": s.kelly_fraction,
            "offline": s.llm_provider == LLMProvider.OFFLINE,
        }

    def available_strategies(self) -> list[dict[str, str]]:
        descriptions = {
            "multi_agent": "Full multi-agent debate + risk pipeline",
            "momentum": "Time-series momentum, vol-targeted",
            "mean_reversion": "RSI dip-buyer / strength-seller",
            "bollinger_breakout": "Bollinger-band breakout follower",
            "ensemble": "Confidence-weighted blend of technicals",
            "sma_crossover": "Fast/slow SMA crossover",
            "buy_and_hold": "Always fully invested baseline",
        }
        names = ["multi_agent", *BASELINE_STRATEGIES.keys()]
        return [{"name": n, "description": descriptions.get(n, n)} for n in names]

    # -- core operations ----------------------------------------------------
    def analyze(
        self,
        symbol: str,
        *,
        lookback_days: int = 365,
        news: list[str] | None = None,
        debate_rounds: int = 2,
        record: bool = False,
    ) -> dict[str, Any]:
        """Run the multi-agent pipeline and return a serialisable report."""

        pipeline = TradingPipeline(self.settings, debate_rounds=debate_rounds)
        result = pipeline.analyze(
            symbol, lookback_days=lookback_days, news=news, record=record
        )
        decision: TradeDecision = result.decision
        return {
            "symbol": result.symbol,
            "decision": decision.model_dump(mode="json"),
            "summary": result.summary(),
            "reports": [r.model_dump(mode="json") for r in result.reports],
            "debate": result.debate.model_dump(mode="json") if result.debate else None,
            "risk": result.risk.model_dump(mode="json") if result.risk else None,
            "indicators": result.indicators,
            "memory_lessons": result.memory_lessons,
        }

    def backtest(
        self,
        symbol: str,
        *,
        days: int = 500,
        rebalance_every: int = 21,
        strategies: list[str] | None = None,
    ) -> dict[str, Any]:
        """Backtest one or more strategies and return metrics + equity curves."""

        history = get_market_provider(self.settings).history(symbol, lookback_days=days)
        engine = Backtester(rebalance_every=rebalance_every)

        requested = strategies or ["multi_agent", "ensemble", "buy_and_hold"]
        built: list[Any] = []
        for name in requested:
            if name == "multi_agent":
                quiet = self.settings.model_copy(update={"verbose": False})
                built.append(AgentStrategy(TradingPipeline(quiet)))
            elif name in BASELINE_STRATEGIES:
                built.append(BASELINE_STRATEGIES[name]())

        results: list[dict[str, Any]] = []
        for strat in built:
            res: BacktestResult = engine.run(history, strat)
            results.append(
                {
                    "strategy": res.strategy,
                    "metrics": res.metrics.to_dict(),
                    "equity_curve": _sample_curve(res.equity_curve),
                    "num_trades": len(res.trades),
                    "trades": res.trades[-50:],
                }
            )
        return {"symbol": symbol.upper(), "days": days, "results": results}
