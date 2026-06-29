# trading_agents

An **advanced multi-agent AI system for financial trading research**. A team of
specialised LLM-backed agents independently analyse an asset, **debate** the bull
and bear cases, size the position under a **risk mandate**, and produce a single
actionable trade decision — which you can then **backtest** against baselines.

> ⚠️ **Educational/research project.** Nothing here is investment advice. The
> default data is *synthetic*. Do not trade real money based on this code.

It runs **fully offline and deterministically** out of the box (no API keys, no
network), and transparently upgrades to live LLMs (OpenAI / Anthropic) and live
market data (yfinance) by changing configuration only.

---

## Why "multi-agent"?

Instead of asking one model "should I buy AAPL?", we decompose the problem the
way a real investment desk does, and make the agents *argue*:

```
                      ┌──────────────────┐
                 ┌───▶│ Technical Analyst│──┐
                 │    ├──────────────────┤  │
   ┌─────────┐   ├───▶│Fundamental Analyst│ │   ┌──────────────┐   ┌──────────┐   ┌───────────────────┐
   │  Market │──▶│    ├──────────────────┤  ├──▶│ Bull vs Bear │──▶│   Risk   │──▶│ Portfolio Manager │──▶ DECISION
   │  Data   │   ├───▶│Sentiment Analyst │  │   │   Debate     │   │  Manager │   │ (final authority) │
   └─────────┘   │    ├──────────────────┤  │   └──────────────┘   └──────────┘   └───────────────────┘
                 └───▶│  Macro Analyst   │──┘          │                  │                 │
                      └──────────────────┘             ▼                  ▼                 ▼
                                            confidence-weighted     vol-targeted      respects risk
                                              conviction +/-1       position sizing    approval & sizing
                                                                                            │
                                                                                            ▼
                                                                                   ┌──────────────────┐
                                                                                   │ Reflection Memory│ (learns from
                                                                                   └──────────────────┘  past trades)
```

### Advanced techniques used here

| Technique | Where | What it gives you |
|---|---|---|
| **Specialised agent roles** | `agents/analysts.py` | Five decorrelated views: price, value, sentiment, macro **and order-flow** |
| **Adversarial debate** (bull vs bear + judge) | `agents/researchers.py` | Reduces single-model bias; surfaces both sides before committing |
| **Confidence-weighted aggregation w/ disagreement shrinkage** | `researchers.py` | Conviction is tempered when analysts disagree |
| **Vol-target + fractional-Kelly sizing** | `agents/risk.py` | Risk-parity sizing blended with a tempered Kelly bet |
| **ATR-based adaptive stops** | `agents/risk.py` | Stop/target widths scale with each name's true range |
| **Risk veto + guardrails** | `agents/risk.py` | The PM *cannot* override a risk rejection |
| **Parallel DAG orchestration** | `orchestration/graph.py` | Independent agents run concurrently; deterministic merge |
| **Reflection memory** | `memory/store.py` | Agents recall lessons from past resolved trades |
| **Provider-agnostic LLM layer w/ offline fallback** | `llm/` | Same code runs deterministically offline or on GPT/Claude |
| **Walk-forward backtester (no look-ahead)** | `backtest/` | Honest evaluation vs momentum, mean-reversion, ensemble & more |
| **Service layer + REST API + web dashboard** | `service.py`, `api/`, `web/` | One facade, two transports (CLI + HTTP), a live UI |

---

## Quickstart

```bash
# 1. Create a virtual environment and install
python -m venv .venv && source .venv/bin/activate
pip install -e .            # core (offline mode works immediately)

# 2. Analyse a symbol (uses synthetic data, no keys needed)
trading-agents analyze AAPL

# 3. Backtest the agent strategy vs baselines
trading-agents backtest MSFT --days 500

# 4. Inspect the active configuration
trading-agents config
```

### Web dashboard + REST API

A modern, buildless dashboard (vanilla JS + Chart.js) and a FastAPI backend ship
in the box:

```bash
pip install -e ".[web]"
trading-agents serve                 # http://127.0.0.1:8000
```

Open the URL to analyse symbols and run multi-strategy backtests interactively.
The REST API is self-documenting at `/docs` and exposes:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/config` | Active configuration |
| `GET` | `/api/strategies` | Available strategies |
| `POST` | `/api/analyze` | Run the multi-agent pipeline for a symbol |
| `POST` | `/api/backtest` | Backtest one or more strategies |

### Architecture document (PDF)

```bash
pip install -e ".[docs]"
python docs/generate_architecture_pdf.py   # writes docs/architecture.pdf
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the generated
[`docs/architecture.pdf`](docs/architecture.pdf) for the full design.

Run the tests:

```bash
pip install -e ".[dev]"
pytest            # 46 tests, all offline & deterministic
ruff check .
```

Or drive it from Python:

```python
from trading_agents.config import Settings
from trading_agents.orchestration import TradingPipeline

pipeline = TradingPipeline(Settings(verbose=True))
result = pipeline.analyze("AAPL", news=["beats earnings, record growth"])
print(result.summary())          # AAPL: BUY weight=27.41% conf=0.42
print(result.decision.rationale)
```

---

## Build it step by step

The codebase is organised so you can read/build it in the same order it was
designed. Each phase is independently useful and testable.

### Phase 0 — Configuration (`config.py`)
A single `pydantic-settings` object reads everything from env vars / `.env`,
with safe defaults so the system runs with zero config. Switch backends here:
`TA_LLM_PROVIDER`, `TA_DATA_SOURCE`, etc.

### Phase 1 — Data layer (`data/`)
* `market.py` — a `MarketDataProvider` interface with two backends: a
  deterministic **synthetic GBM generator** (no network) and **yfinance** for
  real data. Both return the same `PriceHistory`.
* `indicators.py` — SMA/EMA/RSI/MACD/Bollinger plus a compact `IndicatorSnapshot`
  (trend, momentum, volatility) that is what we actually feed to agents.

### Phase 2 — LLM abstraction (`llm/`)
A `ChatModel` interface hides OpenAI/Anthropic/offline differences. The key idea:
every agent computes a **complete heuristic decision** first; the LLM is asked to
*improve* it via `structured()`. Offline, the heuristic *is* the decision — so the
whole system is reproducible and CI-friendly with **no API key**.

### Phase 3 — Analyst agents (`agents/analysts.py`)
Five agents, each emitting a signal in `[-1, 1]` + confidence + rationale:
technical, fundamental (pseudo-fundamentals offline), sentiment (scores
headlines, or a price-confirmed proxy), macro (volatility regime), and **flow**
(OBV / relative-volume / Bollinger-position — i.e. is the move *confirmed* by
participation). They are independent, so the orchestrator runs them concurrently.

### Phase 4 — Adversarial research + risk + execution
* `researchers.py` — a **bull** and a **bear** argue over N rounds using the
  analysts' evidence; a judge outputs a net **conviction** (confidence-weighted,
  shrunk by disagreement).
* `risk.py` — translates conviction + volatility into a position using a blend of
  **vol-targeting** and **fractional Kelly**, with **ATR-based** stops/targets,
  and can **veto** the trade.
* `trader.py` — the Portfolio Manager makes the final call, *bound* by the risk
  mandate.

### Phase 5 — Reflection memory (`memory/`)
A file-backed episodic memory. After a trade resolves, it stores what/why/outcome
and distils a one-line **lesson**, recalled before the next decision on that
symbol. A transparent, offline stand-in for a vector store.

### Phase 6 — Orchestration (`orchestration/`)
* `graph.py` — a tiny dependency-graph engine (à la LangGraph) that resolves a
  topological order, groups nodes into dependency **levels**, and runs each
  level — executing independent nodes **concurrently** with a deterministic,
  name-sorted merge. Detects cycles & missing deps.
* `pipeline.py` — wires the agents into the graph and exposes `analyze()`.

### Phase 7 — Backtesting (`backtest/`)
* `portfolio.py` — cash + positions, target-weight rebalancing with commissions
  and stop/target exits.
* `engine.py` — **walk-forward** simulation that only ever shows a strategy the
  history available up to each decision date (**no look-ahead**).
* `metrics.py` — total return, CAGR, Sharpe, Sortino, max drawdown, Calmar, win rate.
* `strategies.py` — `AgentStrategy` (the full pipeline) plus `Momentum`,
  `MeanReversion`, `BollingerBreakout`, a confidence-weighted `Ensemble`, and the
  `BuyAndHold` / `MovingAverageCrossover` baselines.

### Phase 8 — Interfaces (`cli.py`, `service.py`, `api/`, `web/`)
* `service.py` — a framework-agnostic facade returning JSON-ready dicts.
* `cli.py` — a `typer` + `rich` interface: `analyze`, `backtest`, `serve`,
  `config`, `version`.
* `api/` + `web/` — a FastAPI backend serving a modern, buildless dashboard.

---

## Going live

Everything below is **optional**. Copy `.env.example` to `.env` and edit:

**Live LLM reasoning (OpenAI):**
```bash
pip install -e ".[openai]"
export TA_LLM_PROVIDER=openai
export TA_LLM_MODEL=gpt-4o-mini
export OPENAI_API_KEY=sk-...
```

**Live LLM reasoning (Anthropic):**
```bash
pip install -e ".[anthropic]"
export TA_LLM_PROVIDER=anthropic
export TA_LLM_MODEL=claude-3-5-sonnet-latest
export ANTHROPIC_API_KEY=...
```

**Real market data:**
```bash
pip install -e ".[data]"
export TA_DATA_SOURCE=yfinance
```

**Everything (data + LLMs + web + docs):**
```bash
pip install -e ".[all]"
```

If a live provider is selected but its key is missing, the system **degrades
gracefully** back to offline mode instead of crashing.

---

## Project layout

```
trading_agents/
├── config.py              # settings (pydantic): provider, risk policy, workers
├── data/                  # market data + indicators (incl. ATR, OBV, flow)
├── llm/                   # provider-agnostic chat (offline/openai/anthropic)
├── agents/                # 5 analysts, debate, risk, trader + typed schemas
├── memory/                # reflection memory
├── orchestration/         # parallel DAG engine + trading pipeline
├── backtest/              # portfolio, engine, metrics, strategies
├── service.py             # framework-agnostic facade (JSON-ready results)
├── api/                   # FastAPI app (REST endpoints + static hosting)
├── web/                   # buildless dashboard (index.html, app.js, styles.css)
└── cli.py                 # typer CLI (analyze, backtest, serve, config)
docs/                      # ARCHITECTURE.md + reproducible architecture PDF
examples/run_pipeline.py   # end-to-end demo
tests/                     # 46 offline, deterministic tests
```

---

## Ideas to extend it

- Multi-asset portfolio optimisation (correlations, sector caps, gross/net limits)
- A real vector store for memory + retrieval-augmented analyst context
- Tool-using agents (SEC filings, earnings transcripts, options flow)
- Parallel async analyst execution and an LLM "judge" that scores the debate
- Live news/sentiment feeds; intraday bars; transaction-cost & slippage models
- Reinforcement learning over the conviction → sizing policy

## License

MIT. For research and educational use only — **not** investment advice.
