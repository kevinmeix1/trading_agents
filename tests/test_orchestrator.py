import pytest

from trading_agents.bootstrap import build_orchestrator
from trading_agents.core.blackboard import PipelineContext
from trading_agents.core.events import EventType
from trading_agents.schemas import TradeAction
from trading_agents.tools.market_data import SimulatedMarketData


@pytest.fixture
def market_data():
    return SimulatedMarketData()


@pytest.fixture
def orchestrator(market_data):
    return build_orchestrator(market_data=market_data)


@pytest.mark.asyncio
async def test_pipeline_completes(orchestrator, market_data):
    snapshot = await market_data.get_snapshot("SPY")
    ctx = PipelineContext(symbol="SPY", snapshot=snapshot)
    result = await orchestrator.run(ctx)

    assert result.run_id == ctx.run_id
    assert result.symbol == "SPY"
    assert result.regime
    assert result.verdict is not None
    assert result.proposal is not None
    events = orchestrator.event_bus.history(result.run_id)
    assert any(e.type == EventType.PIPELINE_STARTED for e in events)
    assert any(e.type == EventType.PIPELINE_COMPLETE for e in events)


@pytest.mark.asyncio
async def test_risk_gate_blocks_low_confidence(orchestrator, market_data):
    from trading_agents.schemas import DebateVerdict, TradeProposal

    snapshot = await market_data.get_snapshot("AAPL")
    ctx = PipelineContext(symbol="AAPL", snapshot=snapshot)
    ctx.debate_verdict = DebateVerdict(
        symbol="AAPL", action=TradeAction.BUY, confidence=0.3, synthesis="test"
    )
    ctx.proposal = TradeProposal(
        symbol="AAPL", action=TradeAction.BUY, quantity=10, confidence=0.3, limit_price=190.0
    )
    risk = await orchestrator.risk_gate.assess(ctx)
    assert not risk.approved
    assert any("Confidence" in v for v in risk.violations)


@pytest.mark.asyncio
async def test_blackboard_records_artifacts(orchestrator, market_data):
    snapshot = await market_data.get_snapshot("QQQ")
    ctx = PipelineContext(symbol="QQQ", snapshot=snapshot)
    await orchestrator.run(ctx)

    assert "regime" in orchestrator.blackboard.keys()
    assert orchestrator.blackboard.read("market_analysis") is not None


@pytest.mark.asyncio
async def test_regime_detector(market_data):
    from trading_agents.regime.detector import RegimeDetector

    detector = RegimeDetector(market_data)
    ctx = PipelineContext(symbol="SPY")
    regime = await detector.detect(ctx)
    assert regime.value in {"trending", "mean_reverting", "high_volatility", "crisis", "unknown"}
