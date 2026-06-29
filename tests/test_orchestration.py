from __future__ import annotations

import pytest

from trading_agents.agents.schemas import Action, TradeDecision
from trading_agents.orchestration.graph import Graph
from trading_agents.orchestration.pipeline import PipelineResult, TradingPipeline


def test_graph_topological_order():
    g = Graph()
    order_log = []
    g.add("a", lambda s: order_log.append("a") or {})
    g.add("b", lambda s: order_log.append("b") or {}, deps=["a"])
    g.add("c", lambda s: order_log.append("c") or {}, deps=["b", "a"])
    g.run()
    assert order_log.index("a") < order_log.index("b") < order_log.index("c")


def test_graph_state_threading():
    g = Graph()
    g.add("one", lambda s: {"x": 1})
    g.add("two", lambda s: {"y": s["x"] + 1}, deps=["one"])
    state = g.run()
    assert state == {"x": 1, "y": 2}


def test_graph_detects_cycle():
    g = Graph()
    g.add("a", lambda s: {}, deps=["b"])
    g.add("b", lambda s: {}, deps=["a"])
    with pytest.raises(ValueError):
        g.run()


def test_graph_unknown_dependency():
    g = Graph()
    g.add("a", lambda s: {}, deps=["missing"])
    with pytest.raises(KeyError):
        g.run()


def test_pipeline_end_to_end(settings):
    pipeline = TradingPipeline(settings)
    result = pipeline.analyze("AAPL", lookback_days=200)
    assert isinstance(result, PipelineResult)
    assert isinstance(result.decision, TradeDecision)
    assert result.decision.action in set(Action)
    assert len(result.reports) == 5
    assert result.debate is not None
    assert result.risk is not None


def test_pipeline_is_deterministic(settings):
    r1 = TradingPipeline(settings).analyze("TSLA", lookback_days=200)
    r2 = TradingPipeline(settings).analyze("TSLA", lookback_days=200)
    assert r1.decision.action == r2.decision.action
    assert r1.decision.target_weight == r2.decision.target_weight


def test_pipeline_records_to_memory(settings):
    pipeline = TradingPipeline(settings)
    pipeline.analyze("AAPL", lookback_days=150, record=True)
    assert len(pipeline.memory) == 1
