"""Minimal example: run the multi-agent pipeline and a backtest in code.

    python examples/run_pipeline.py
"""

from __future__ import annotations

from stock_trading_agent.backtest import (
    AgentStrategy,
    Backtester,
    BollingerBreakoutStrategy,
    BuyAndHold,
    EnsembleStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
)
from stock_trading_agent.config import Settings
from stock_trading_agent.data.market import get_market_provider
from stock_trading_agent.orchestration import TradingPipeline
from stock_trading_agent.service import TradingService


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

    # 2) Walk-forward backtest vs baselines and the new strategies.
    print("\n--- Backtest (NVDA, 500d) ---")
    history = get_market_provider(settings).history("NVDA", lookback_days=500)
    engine = Backtester(rebalance_every=21)
    quiet = settings.model_copy(update={"verbose": False})
    for strat in (
        AgentStrategy(TradingPipeline(quiet)),
        MomentumStrategy(),
        MeanReversionStrategy(),
        BollingerBreakoutStrategy(),
        EnsembleStrategy(),
        BuyAndHold(),
    ):
        print(engine.run(history, strat).summary())

    # 3) The same logic via the service layer (what the API/CLI use), returning
    #    plain JSON-ready dicts.
    print("\n--- Service layer (JSON-ready) ---")
    service = TradingService(quiet)
    report = service.analyze("MSFT", lookback_days=300)
    print("MSFT decision:", report["decision"]["action"], report["decision"]["target_weight"])


if __name__ == "__main__":
    main()
