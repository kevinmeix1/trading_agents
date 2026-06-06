from __future__ import annotations

from trading_agents.agents.debate.coordinator import DebateCoordinator
from trading_agents.agents.execution_agent import ExecutionAgent, RiskVetoGate
from trading_agents.agents.market_analyst import MarketAnalyst
from trading_agents.agents.portfolio_manager import PortfolioManager
from trading_agents.agents.sentiment_analyst import SentimentAnalyst
from trading_agents.core.events import EventBus
from trading_agents.core.blackboard import Blackboard
from trading_agents.core.orchestrator import TradingOrchestrator
from trading_agents.regime.detector import RegimeDetector
from trading_agents.tools.market_data import MarketDataProvider, SimulatedMarketData


def build_orchestrator(
    market_data: MarketDataProvider | None = None,
    event_bus: EventBus | None = None,
    blackboard: Blackboard | None = None,
) -> TradingOrchestrator:
    """Factory wiring all agents into the orchestrator."""
    data = market_data or SimulatedMarketData()
    return TradingOrchestrator(
        regime_detector=RegimeDetector(data),
        market_analyst=MarketAnalyst(data),
        sentiment_analyst=SentimentAnalyst(),
        debate_coordinator=DebateCoordinator(),
        portfolio_manager=PortfolioManager(),
        risk_gate=RiskVetoGate(),
        execution_agent=ExecutionAgent(),
        event_bus=event_bus,
        blackboard=blackboard,
    )
