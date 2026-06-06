from __future__ import annotations

import asyncio
import json

import structlog

from trading_agents.bootstrap import build_orchestrator
from trading_agents.config import settings
from trading_agents.core.blackboard import PipelineContext
from trading_agents.memory.episodic import EpisodicMemory
from trading_agents.tools.market_data import SimulatedMarketData


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )


async def run_pipeline(symbol: str) -> dict:
    market_data = SimulatedMarketData()
    orchestrator = build_orchestrator(market_data=market_data)
    memory = EpisodicMemory()

    snapshot = await market_data.get_snapshot(symbol)
    ctx = PipelineContext(symbol=symbol, snapshot=snapshot)
    result = await orchestrator.run(ctx)
    memory.record(result)

    return {
        "run_id": result.run_id,
        "symbol": result.symbol,
        "regime": result.regime,
        "action": result.proposal.action.value if result.proposal else "hold",
        "quantity": result.proposal.quantity if result.proposal else 0,
        "confidence": result.proposal.confidence if result.proposal else 0,
        "blocked": result.blocked,
        "block_reason": result.block_reason,
        "order_status": result.order.status.value if result.order else None,
        "fill_price": result.order.fill_price if result.order else None,
        "events": len(orchestrator.event_bus.history(result.run_id)),
    }


async def run_all(symbols: list[str]) -> list[dict]:
    log = structlog.get_logger()
    results = []
    for symbol in symbols:
        log.info("running_pipeline", symbol=symbol, mode=settings.mode.value)
        results.append(await run_pipeline(symbol))
    return results
