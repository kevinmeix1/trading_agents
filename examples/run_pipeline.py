"""Minimal example: run the multi-agent pipeline and a backtest in code.

    python examples/run_pipeline.py
"""

from __future__ import annotations

from trading_agents.backtest import AgentStrategy, Backtester, BuyAndHold, MovingAverageCrossover
from trading_agents.config import Settings
from trading_agents.data.market import get_market_provider
from trading_agents.orchestration import TradingPipeline


def main() -> None:
    settings = Settings(verbose=True, memory_path="runs/example_memory.json")

    # 1) One-shot decision for a single symbol.
    pipeline = TradingPipeline(settings, debate_rounds=2)
    result = pipeline.analyze(
        "AAPL",
        lookback_days=300,
        news=["Company beats earnings with record growth", "Analyst upgrade to strong buy"],
        record=True,
    )
    print("\nDecision:", result.summary())
    print("Rationale:", result.decision.rationale)

    # 2) Walk-forward backtest vs baselines.
    print("\n--- Backtest (NVDA, 500d) ---")
    history = get_market_provider(settings).history("NVDA", lookback_days=500)
    engine = Backtester(rebalance_every=21)
    quiet = settings.model_copy(update={"verbose": False})
    for strat in (
        AgentStrategy(TradingPipeline(quiet)),
        MovingAverageCrossover(),
        BuyAndHold(),
    ):
        print(engine.run(history, strat).summary())


if __name__ == "__main__":
    main()
