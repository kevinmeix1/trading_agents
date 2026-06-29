"""Adversarial research: a bull and a bear debate, then a judge synthesises.

This is the "advanced" reasoning core. Rather than averaging analyst opinions,
two researchers argue opposite sides using the analyst evidence, optionally over
several rounds. A neutral judge then produces a net *conviction* that downstream
risk and execution agents act on.

The debate text is produced by the LLM (real or offline). The numeric conviction
is computed deterministically from confidence-weighted analyst signals and the
spread of opinion, so it remains robust and testable even offline.
"""

from __future__ import annotations

from rich.console import Console

from stock_trading_agent.agents.base import AgentContext
from stock_trading_agent.agents.schemas import AnalystReport, DebateResult
from stock_trading_agent.config import Settings
from stock_trading_agent.llm.base import ChatModel, Message

_console = Console()


class ResearchDebate:
    role = "research_debate"

    def __init__(self, llm: ChatModel, settings: Settings, rounds: int = 2):
        self.llm = llm
        self.settings = settings
        self.rounds = max(1, rounds)

    @staticmethod
    def _weighted_conviction(reports: list[AnalystReport]) -> tuple[float, float]:
        """Return (conviction, disagreement) from analyst reports."""

        if not reports:
            return 0.0, 0.0
        total_w = sum(r.confidence for r in reports) or 1.0
        weighted = sum(r.signal * r.confidence for r in reports) / total_w
        mean = sum(r.signal for r in reports) / len(reports)
        disagreement = (sum((r.signal - mean) ** 2 for r in reports) / len(reports)) ** 0.5
        # Shrink conviction when analysts strongly disagree.
        conviction = weighted * (1 - min(0.5, disagreement))
        return max(-1.0, min(1.0, conviction)), disagreement

    def _argue(self, side: str, reports: list[AnalystReport], ctx: AgentContext) -> str:
        if side == "bull":
            evidence = [r for r in reports if r.signal >= 0]
            system = (
                "You are the BULL researcher. Argue persuasively for buying, citing "
                "the strongest supportive evidence. Be concise and specific."
            )
        else:
            evidence = [r for r in reports if r.signal < 0]
            system = (
                "You are the BEAR researcher. Argue persuasively for caution/selling, "
                "citing the strongest risks. Be concise and specific."
            )
        if not evidence:
            evidence = reports

        facts = "\n".join(
            f"- {r.agent} | signal: {r.signal:+.2f} | confidence: {r.confidence:.2f} | "
            f"{r.rationale}"
            for r in evidence
        )
        user = f"Symbol: {ctx.symbol}\nEvidence:\n{facts}\nMake your case."
        return self.llm.chat(
            [Message("system", system), Message("user", user)],
            temperature=self.settings.llm_temperature,
        ).strip()

    def run(self, ctx: AgentContext) -> DebateResult:
        reports: list[AnalystReport] = [
            v for v in ctx.scratchpad.values() if isinstance(v, AnalystReport)
        ]
        conviction, disagreement = self._weighted_conviction(reports)

        bull_parts = [self._argue("bull", reports, ctx)]
        bear_parts = [self._argue("bear", reports, ctx)]

        # Additional rebuttal rounds enrich the qualitative case. With a live LLM
        # these become genuine back-and-forth; offline we avoid duplicate text.
        for n in range(2, self.rounds + 1):
            bull_rebuttal = self._argue("bull", reports, ctx)
            bear_rebuttal = self._argue("bear", reports, ctx)
            if bull_rebuttal not in bull_parts:
                bull_parts.append(bull_rebuttal)
            else:
                bull_parts.append(f"(round {n}) The bull stands by the case above.")
            if bear_rebuttal not in bear_parts:
                bear_parts.append(bear_rebuttal)
            else:
                bear_parts.append(f"(round {n}) The bear stands by the case above.")

        bull_thesis = " ".join(bull_parts)
        bear_thesis = " ".join(bear_parts)

        if conviction > 0.15:
            verdict = "leans BULLISH"
        elif conviction < -0.15:
            verdict = "leans BEARISH"
        else:
            verdict = "is INCONCLUSIVE"
        judge_summary = (
            f"After {self.rounds} round(s), the debate {verdict} "
            f"(net conviction {conviction:+.2f}, analyst disagreement {disagreement:.2f})."
        )

        result = DebateResult(
            bull_thesis=bull_thesis,
            bear_thesis=bear_thesis,
            rounds=self.rounds,
            judge_summary=judge_summary,
            conviction=conviction,
        )
        ctx.remember("debate", result)
        if self.settings.verbose:
            _console.print(
                f"[dim]│[/dim] [bold magenta]{self.role}[/bold magenta] {judge_summary}"
            )
        return result
