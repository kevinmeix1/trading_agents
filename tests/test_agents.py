from __future__ import annotations

from stock_trading_agent.agents.analysts import (
    FundamentalAnalyst,
    MacroAnalyst,
    SentimentAnalyst,
    TechnicalAnalyst,
)
from stock_trading_agent.agents.base import AgentContext
from stock_trading_agent.agents.researchers import ResearchDebate
from stock_trading_agent.agents.risk import RiskManager
from stock_trading_agent.agents.schemas import Action, AnalystReport
from stock_trading_agent.agents.trader import PortfolioManager
from stock_trading_agent.data.indicators import compute_indicators
from stock_trading_agent.llm.offline import OfflineChatModel


def _ctx(history, settings, news=None):
    return AgentContext(
        symbol=history.symbol,
        history=history,
        indicators=compute_indicators(history),
        settings=settings,
        news=news or [],
    )


def test_all_analysts_emit_valid_reports(history, settings):
    llm = OfflineChatModel()
    ctx = _ctx(history, settings)
    for cls in (TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, MacroAnalyst):
        report = cls(llm, settings).analyze(ctx)
        assert isinstance(report, AnalystReport)
        assert -1.0 <= report.signal <= 1.0
        assert 0.0 <= report.confidence <= 1.0
        assert report.rationale


def test_sentiment_reacts_to_headlines(history, settings):
    llm = OfflineChatModel()
    pos = SentimentAnalyst(llm, settings).analyze(
        _ctx(history, settings, news=["record growth, strong beat, upgrade"])
    )
    neg = SentimentAnalyst(llm, settings).analyze(
        _ctx(history, settings, news=["lawsuit and downgrade, weak miss, plunge"])
    )
    assert pos.signal > neg.signal


def test_debate_conviction_in_range(history, settings):
    llm = OfflineChatModel()
    ctx = _ctx(history, settings)
    for cls in (TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, MacroAnalyst):
        cls(llm, settings).analyze(ctx)
    debate = ResearchDebate(llm, settings, rounds=2).run(ctx)
    assert -1.0 <= debate.conviction <= 1.0
    assert debate.bull_thesis and debate.bear_thesis


def test_risk_vetoes_low_conviction(history, settings):
    llm = OfflineChatModel()
    ctx = _ctx(history, settings)
    # No analysts/debate => zero conviction => risk should not approve.
    assessment = RiskManager(llm, settings).assess(ctx)
    assert assessment.approved is False
    assert assessment.position_size_pct == 0.0


def test_risk_caps_position_size(history, settings):
    llm = OfflineChatModel()
    ctx = _ctx(history, settings)
    ctx.remember(
        "tech",
        AnalystReport(agent="t", signal=1.0, confidence=1.0, rationale="max bull"),
    )
    ResearchDebate(llm, settings).run(ctx)
    rm = RiskManager(llm, settings, max_position=0.25)
    assessment = rm.assess(ctx)
    assert assessment.position_size_pct <= 0.25


def test_trader_holds_when_risk_rejects(history, settings):
    llm = OfflineChatModel()
    ctx = _ctx(history, settings)
    ResearchDebate(llm, settings).run(ctx)
    RiskManager(llm, settings).assess(ctx)
    decision = PortfolioManager(llm, settings).decide(ctx)
    assert decision.action == Action.HOLD
    assert decision.target_weight == 0.0
