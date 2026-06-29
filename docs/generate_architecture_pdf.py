"""Generate ``docs/architecture.pdf`` — a polished architecture document.

The PDF is produced entirely with reportlab (no external image assets), so it is
fully reproducible:

    pip install -e ".[docs]"
    python docs/generate_architecture_pdf.py

A vector architecture diagram is drawn with reportlab's graphics primitives and
embedded as a flowable alongside the prose.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Palette mirrors the web dashboard for a consistent brand.
INK = colors.HexColor("#0f1525")
ACCENT = colors.HexColor("#5b8cff")
ACCENT2 = colors.HexColor("#9b6bff")
GREEN = colors.HexColor("#2fd47a")
RED = colors.HexColor("#ff5d6c")
YELLOW = colors.HexColor("#e0a93b")
MUTED = colors.HexColor("#5b6680")
CARD = colors.HexColor("#eef1f8")
LINE = colors.HexColor("#c7d0e2")

OUT = Path(__file__).resolve().parent / "architecture.pdf"


class PipelineDiagram(Flowable):
    """A vector diagram of the multi-agent decision pipeline."""

    def __init__(self, width: float, height: float = 150 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, c, x, y, w, h, label, fill, sub=None, text=colors.white):
        c.setFillColor(fill)
        c.setStrokeColor(fill)
        c.roundRect(x, y, w, h, 4, fill=1, stroke=0)
        c.setFillColor(text)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(x + w / 2, y + h / 2 + (2 if sub else -3), label)
        if sub:
            c.setFont("Helvetica", 6.5)
            c.drawCentredString(x + w / 2, y + h / 2 - 7, sub)

    def _arrow(self, c, x1, y1, x2, y2):
        c.setStrokeColor(LINE)
        c.setLineWidth(1.3)
        c.line(x1, y1, x2, y2)
        c.setFillColor(LINE)
        ah = 3
        if abs(x2 - x1) >= abs(y2 - y1):  # horizontal-ish
            d = 1 if x2 >= x1 else -1
            c.lines([(x2, y2, x2 - d * ah, y2 + ah), (x2, y2, x2 - d * ah, y2 - ah)])
        else:  # vertical-ish
            d = 1 if y2 >= y1 else -1
            c.lines([(x2, y2, x2 - ah, y2 - d * ah), (x2, y2, x2 + ah, y2 - d * ah)])

    def draw(self):
        c = self.canv
        # Column x positions, laid out to fit within the flowable width.
        bw = 28 * mm
        ah = 9 * mm
        gap = (self.width - 5 * bw) / 4  # even gaps between five columns
        x_data = 0
        x_analyst = x_data + bw + gap
        x_debate = x_analyst + bw + gap
        x_risk = x_debate + bw + gap
        x_pm = x_risk + bw + gap

        top = self.height - 12 * mm
        analysts = [
            ("Technical", ACCENT),
            ("Fundamental", ACCENT),
            ("Sentiment", ACCENT),
            ("Macro", ACCENT),
            ("Flow", ACCENT),
        ]
        # Data source box (vertically centred).
        mid = top - (len(analysts) * (ah + 4 * mm)) / 2 + ah
        self._box(c, x_data, mid, bw, ah, "Market Data", ACCENT2, sub="OHLCV + indicators")

        analyst_centres = []
        for i, (name, col) in enumerate(analysts):
            y = top - i * (ah + 4 * mm)
            self._box(c, x_analyst, y, bw, ah, name, col, sub="signal [-1,1]")
            cy = y + ah / 2
            analyst_centres.append(cy)
            self._arrow(c, x_data + bw, mid + ah / 2, x_analyst, cy)

        # Debate.
        debate_y = top - (len(analysts) - 1) * (ah + 4 * mm) / 2 - ah / 2
        dh = 16 * mm
        self._box(c, x_debate, debate_y, bw, dh, "Debate", ACCENT2, sub="bull vs bear + judge")
        for cy in analyst_centres:
            self._arrow(c, x_analyst + bw, cy, x_debate, debate_y + dh / 2)

        cy_chain = debate_y + dh / 2
        self._box(c, x_risk, cy_chain - ah / 2, bw, ah, "Risk", YELLOW,
                  sub="vol-target + Kelly", text=INK)
        self._arrow(c, x_debate + bw, cy_chain, x_risk, cy_chain)
        self._box(c, x_pm, cy_chain - ah / 2, bw, ah, "Portfolio Mgr", GREEN,
                  sub="final decision", text=INK)
        self._arrow(c, x_risk + bw, cy_chain, x_pm, cy_chain)

        # Decision output below the PM.
        dec_y = cy_chain - ah / 2 - 16 * mm
        self._box(c, x_pm, dec_y, bw, ah, "BUY / SELL / HOLD", INK)
        self._arrow(c, x_pm + bw / 2, cy_chain - ah / 2, x_pm + bw / 2, dec_y + ah)

        # Memory feedback loop.
        mem_y = dec_y - 2 * mm
        self._box(c, x_debate, mem_y, bw, ah, "Reflection Memory", ACCENT,
                  sub="learns from trades")
        self._arrow(c, x_pm, dec_y + ah / 2, x_debate + bw, mem_y + ah / 2)
        self._arrow(c, x_debate, mem_y + ah / 2, x_data + bw / 2, mem_y + ah / 2)
        self._arrow(c, x_data + bw / 2, mem_y + ah / 2, x_data + bw / 2, mid)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverTitle", parent=ss["Title"], fontSize=30, textColor=INK,
                          spaceAfter=6, leading=34))
    ss.add(ParagraphStyle("CoverSub", parent=ss["Normal"], fontSize=13, textColor=ACCENT,
                          alignment=TA_CENTER, spaceAfter=2))
    ss.add(ParagraphStyle("CoverNote", parent=ss["Normal"], fontSize=9.5,
                          textColor=colors.HexColor("#5b6680"), alignment=TA_CENTER))
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], fontSize=16, textColor=INK,
                          spaceBefore=14, spaceAfter=8))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, textColor=ACCENT2,
                          spaceBefore=10, spaceAfter=5))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10, leading=15,
                          textColor=colors.HexColor("#1b2230"), spaceAfter=6))
    ss.add(ParagraphStyle("Caption", parent=ss["Normal"], fontSize=8.5,
                          textColor=colors.HexColor("#5b6680"), alignment=TA_CENTER,
                          spaceBefore=4))
    return ss


def _bullets(items, ss):
    return ListFlowable(
        [ListItem(Paragraph(t, ss["Body"]), leftIndent=10) for t in items],
        bulletColor=ACCENT, bulletType="bullet", start="•", leftIndent=14,
    )


def _table(rows, ss, col_widths):
    data = [[Paragraph(f"<b>{c}</b>" if i == 0 else c, ss["Body"]) for c in row]
            for i, row in enumerate(rows)]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    # White header text.
    for r in range(len(data)):
        for cidx in range(len(data[r])):
            if r == 0:
                data[r][cidx] = Paragraph(
                    f'<font color="white"><b>{rows[r][cidx]}</b></font>', ss["Body"])
    return t


def build(out: Path | str = OUT) -> Path:
    out = Path(out)
    ss = _styles()
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm,
        title="trading_agents — Architecture", author="trading_agents",
    )
    story: list = []

    # --- Cover ---
    story.append(Spacer(1, 55 * mm))
    story.append(Paragraph("trading_agents", ss["CoverTitle"]))
    story.append(Paragraph("Multi-Agent AI Trading System — Architecture", ss["CoverSub"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "A team of specialised LLM-backed agents that analyse, debate, size under a "
        "risk mandate, and decide — then prove it on a walk-forward backtester.",
        ss["CoverNote"]))
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph(
        "Educational / research only — not investment advice. "
        "Runs fully offline and deterministically by default.", ss["CoverNote"]))
    story.append(PageBreak())

    # --- 1. Overview ---
    story.append(Paragraph("1. System Overview", ss["H1"]))
    story.append(Paragraph(
        "<b>trading_agents</b> decomposes the question &ldquo;should I trade this "
        "asset?&rdquo; the way an investment desk does. Specialised agents form "
        "independent views, two researchers debate the bull and bear cases, a risk "
        "officer sizes the position under a hard mandate, and a portfolio manager "
        "issues the final decision. The identical decision function plugs straight "
        "into a walk-forward backtester for honest evaluation against baselines.",
        ss["Body"]))
    story.append(Paragraph(
        "The system is organised in small, typed, independently testable layers. It "
        "runs offline and deterministically out of the box and upgrades to live LLMs "
        "and live market data by configuration only.", ss["Body"]))

    story.append(Paragraph("2. Decision Pipeline", ss["H1"]))
    story.append(Paragraph(
        "Market data feeds five independent analysts (run concurrently). Their "
        "evidence drives an adversarial debate that yields a net conviction; risk "
        "translates that into a vol- and Kelly-aware position with ATR stops; the "
        "portfolio manager issues the bounded decision and resolved trades feed "
        "reflection memory.", ss["Body"]))
    story.append(PipelineDiagram(doc.width))
    story.append(Paragraph(
        "Figure 1 — End-to-end multi-agent decision pipeline with risk veto and "
        "reflection-memory feedback loop.", ss["Caption"]))
    story.append(PageBreak())

    # --- 3. Layers ---
    story.append(Paragraph("3. Layered Architecture", ss["H1"]))
    story.append(Paragraph(
        "Each layer exposes a small contract, so any layer can be tested or replaced "
        "in isolation. The service layer is the seam between business logic and "
        "transport: the CLI and HTTP API both build on it.", ss["Body"]))
    story.append(_table([
        ["Layer", "Package", "Responsibility"],
        ["Configuration", "config.py", "Typed settings from env / .env (pydantic)"],
        ["Data", "data/", "Market data providers + technical indicators"],
        ["LLM abstraction", "llm/", "Provider-agnostic chat with offline fallback"],
        ["Agents", "agents/", "Analysts, debate, risk, portfolio manager"],
        ["Memory", "memory/", "File-backed reflection memory"],
        ["Orchestration", "orchestration/", "DAG engine + end-to-end pipeline"],
        ["Backtest", "backtest/", "Portfolio, engine, metrics, strategies"],
        ["Service", "service.py", "Framework-agnostic JSON facade"],
        ["Interfaces", "cli.py, api/, web/", "CLI, REST API, web dashboard"],
    ], ss, [32 * mm, 34 * mm, doc.width - 66 * mm]))

    story.append(Paragraph("4. Orchestration Engine", ss["H1"]))
    story.append(Paragraph(
        "A dependency-graph (DAG) engine validates the wiring (detecting cycles and "
        "missing dependencies), computes dependency levels, and runs each level — "
        "executing mutually-independent nodes concurrently on a thread pool. Updates "
        "are merged back in a stable, name-sorted order, so a parallel run is "
        "identical to a sequential one. This is a real latency win for live-LLM runs "
        "while preserving determinism.", ss["Body"]))

    story.append(Paragraph("5. Determinism &amp; the LLM Abstraction", ss["H1"]))
    story.append(Paragraph(
        "Every agent first computes a complete heuristic decision from the data; the "
        "LLM is asked only to improve it. Offline, the heuristic is the decision, so "
        "the whole system is reproducible with no API key. A missing provider key "
        "degrades gracefully back to offline mode rather than crashing.", ss["Body"]))
    story.append(PageBreak())

    # --- 6. Risk + strategies ---
    story.append(Paragraph("6. Risk &amp; Position Sizing", ss["H1"]))
    story.append(_bullets([
        "<b>Volatility targeting</b> — scale exposure so expected position "
        "volatility matches a target, instead of fixed bet sizes.",
        "<b>Fractional Kelly</b> — blend in a tempered Kelly bet "
        "(edge / variance) governed by a configurable fraction.",
        "<b>ATR-based stops</b> — stop-loss / take-profit widths adapt to each "
        "name&rsquo;s true range.",
        "<b>Hard veto</b> — the risk officer can reject a trade and cap any single "
        "position; the portfolio manager cannot override it.",
    ], ss))

    story.append(Paragraph("7. Strategies &amp; Backtesting", ss["H1"]))
    story.append(Paragraph(
        "The walk-forward engine only ever shows a strategy the history available up "
        "to each decision date (no look-ahead), marks to market daily, and honours "
        "stops. Metrics: total return, CAGR, Sharpe, Sortino, max drawdown, Calmar "
        "and win rate.", ss["Body"]))
    story.append(_table([
        ["Strategy", "Idea"],
        ["multi_agent", "Full debate + risk pipeline"],
        ["momentum", "Time-series momentum, vol-targeted"],
        ["mean_reversion", "RSI dip-buyer / strength-seller"],
        ["bollinger_breakout", "Trade closes beyond the bands"],
        ["ensemble", "Confidence-weighted blend of technicals"],
        ["sma_crossover / buy_and_hold", "Classic baselines"],
    ], ss, [55 * mm, doc.width - 55 * mm]))

    story.append(Paragraph("8. Interfaces &amp; Extensibility", ss["H1"]))
    story.append(_bullets([
        "<b>CLI</b> — analyze, backtest, serve, config, version.",
        "<b>REST API</b> — FastAPI with typed request models and OpenAPI docs.",
        "<b>Web dashboard</b> — buildless SPA (vanilla JS + Chart.js).",
        "<b>Extend</b> — new analysts implement BaseAgent; new strategies implement "
        "the Strategy protocol; new data/LLM providers implement their interfaces.",
    ], ss))

    doc.build(story)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")
