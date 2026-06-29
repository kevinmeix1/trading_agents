"""The end-to-end multi-agent trading pipeline.

Wires the agents into a graph and runs them for a single symbol:

    data ─▶ ┌ technical ┐
            │ fundamental│
            │ sentiment  │─▶ debate ─▶ risk ─▶ portfolio_manager ─▶ decision
            └ macro     ┘

The analyst nodes are independent and could run in parallel; here they run in
dependency order for deterministic, debuggable output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from trading_agents.agents.analysts import (
    FlowAnalyst,
    FundamentalAnalyst,
    MacroAnalyst,
    SentimentAnalyst,
    TechnicalAnalyst,
)
from trading_agents.agents.base import AgentContext
from trading_agents.agents.researchers import ResearchDebate
from trading_agents.agents.risk import RiskManager
from trading_agents.agents.schemas import AnalystReport, DebateResult, RiskAssessment, TradeDecision
from trading_agents.agents.trader import PortfolioManager
from trading_agents.config import Settings, get_settings
from trading_agents.data.indicators import compute_indicators
from trading_agents.data.market import MarketDataProvider, get_market_provider
from trading_agents.llm.base import ChatModel
from trading_agents.llm.factory import get_chat_model
from trading_agents.memory.store import ReflectionMemory
from trading_agents.orchestration.graph import Graph

_console = Console()


@dataclass
class PipelineResult:
    symbol: str
    decision: TradeDecision
    reports: list[AnalystReport] = field(default_factory=list)
    debate: DebateResult | None = None
    risk: RiskAssessment | None = None
    indicators: dict[str, Any] = field(default_factory=dict)
    memory_lessons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        d = self.decision
        return (
            f"{self.symbol}: {d.action.value} weight={d.target_weight:.2%} "
            f"conf={d.confidence:.2f}"
        )


class TradingPipeline:
    """Construct once, then call :meth:`analyze` for any symbol."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: ChatModel | None = None,
        provider: MarketDataProvider | None = None,
        memory: ReflectionMemory | None = None,
        debate_rounds: int = 2,
    ):
        self.settings = settings or get_settings()
        self.llm = llm or get_chat_model(self.settings)
        self.provider = provider or get_market_provider(self.settings)
        self.memory = memory or ReflectionMemory(self.settings.memory_path)

        self.technical = TechnicalAnalyst(self.llm, self.settings)
        self.fundamental = FundamentalAnalyst(self.llm, self.settings)
        self.sentiment = SentimentAnalyst(self.llm, self.settings)
        self.macro = MacroAnalyst(self.llm, self.settings)
        self.flow = FlowAnalyst(self.llm, self.settings)
        self.debate = ResearchDebate(self.llm, self.settings, rounds=debate_rounds)
        self.risk = RiskManager(
            self.llm,
            self.settings,
            target_volatility=self.settings.target_volatility,
            max_position=self.settings.max_position,
            kelly_fraction=self.settings.kelly_fraction,
        )
        self.manager = PortfolioManager(self.llm, self.settings)

    def _build_graph(self) -> Graph:
        # The four (now five) analysts are mutually independent, so they form a
        # single dependency level that the engine can evaluate concurrently.
        g = Graph(max_workers=self.settings.max_workers)

        def ctx(state: dict[str, Any]) -> AgentContext:
            return state["ctx"]

        g.add("technical", lambda s: {"technical": self.technical.analyze(ctx(s))})
        g.add("fundamental", lambda s: {"fundamental": self.fundamental.analyze(ctx(s))})
        g.add("sentiment", lambda s: {"sentiment": self.sentiment.analyze(ctx(s))})
        g.add("macro", lambda s: {"macro": self.macro.analyze(ctx(s))})
        g.add("flow", lambda s: {"flow": self.flow.analyze(ctx(s))})
        g.add(
            "debate",
            lambda s: {"_": self.debate.run(ctx(s))},
            deps=["technical", "fundamental", "sentiment", "macro", "flow"],
        )
        g.add("risk", lambda s: {"_": self.risk.assess(ctx(s))}, deps=["debate"])
        g.add(
            "decision",
            lambda s: {"decision": self.manager.decide(ctx(s))},
            deps=["risk"],
        )
        return g

    def analyze(
        self,
        symbol: str,
        *,
        lookback_days: int = 365,
        news: list[str] | None = None,
        record: bool = False,
    ) -> PipelineResult:
        """Run the full agent pipeline for ``symbol`` and return the decision."""

        history = self.provider.history(symbol, lookback_days=lookback_days)
        return self.analyze_history(history, news=news, record=record)

    def analyze_history(
        self,
        history,
        *,
        news: list[str] | None = None,
        record: bool = False,
    ) -> PipelineResult:
        """Run the pipeline against an already-fetched price history.

        Used by the backtester, which slices history as it walks forward in time.
        """

        symbol = history.symbol
        indicators = compute_indicators(history)
        lessons = self.memory.recall(symbol)

        agent_ctx = AgentContext(
            symbol=symbol.upper(),
            history=history,
            indicators=indicators,
            settings=self.settings,
            news=news or [],
            memory_notes=lessons,
        )

        if self.settings.verbose:
            _console.rule(f"[bold]Analyzing {symbol.upper()}[/bold]")

        state = self._build_graph().run({"ctx": agent_ctx})
        decision: TradeDecision = state["decision"]

        result = PipelineResult(
            symbol=symbol.upper(),
            decision=decision,
            reports=[v for v in agent_ctx.scratchpad.values() if isinstance(v, AnalystReport)],
            debate=agent_ctx.scratchpad.get("debate"),
            risk=agent_ctx.scratchpad.get("risk"),
            indicators=indicators.to_dict(),
            memory_lessons=lessons,
        )

        if record:
            self.memory.record_decision(
                symbol=symbol,
                action=decision.action.value,
                conviction=result.debate.conviction if result.debate else 0.0,
                rationale=decision.rationale,
            )
        return result
