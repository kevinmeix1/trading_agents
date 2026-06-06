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
| **Specialised agent roles** | `agents/analysts.py` | Diverse, decorrelated views (price, value, sentiment, macro) |
| **Adversarial debate** (bull vs bear + judge) | `agents/researchers.py` | Reduces single-model bias; surfaces both sides before committing |
| **Confidence-weighted aggregation w/ disagreement shrinkage** | `researchers.py` | Conviction is tempered when analysts disagree |
| **Volatility-targeted position sizing** | `agents/risk.py` | Risk-parity-style sizing instead of fixed bets |
| **Risk veto + guardrails (stops/targets)** | `agents/risk.py` | The PM *cannot* override a risk rejection |
| **Graph orchestration (DAG)** | `orchestration/graph.py` | Explicit dependencies, topological execution, testable |
| **Reflection memory** | `memory/store.py` | Agents recall lessons from past resolved trades |
| **Provider-agnostic LLM layer w/ offline fallback** | `llm/` | Same code runs deterministically offline or on GPT/Claude |
| **Walk-forward backtester (no look-ahead)** | `backtest/` | Honest evaluation vs Buy&Hold and SMA-crossover |

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

Run the tests:

```bash
pip install -e ".[dev]"
pytest            # 36 tests, all offline & deterministic
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
Four agents, each emitting a signal in `[-1, 1]` + confidence + rationale:
technical, fundamental (pseudo-fundamentals offline), sentiment (scores
headlines, or a price-confirmed proxy), and macro (volatility regime).

### Phase 4 — Adversarial research + risk + execution
* `researchers.py` — a **bull** and a **bear** argue over N rounds using the
  analysts' evidence; a judge outputs a net **conviction** (confidence-weighted,
  shrunk by disagreement).
* `risk.py` — translates conviction + volatility into a **vol-targeted** position
  size with stops/targets, and can **veto** the trade.
* `trader.py` — the Portfolio Manager makes the final call, *bound* by the risk
  mandate.

### Phase 5 — Reflection memory (`memory/`)
A file-backed episodic memory. After a trade resolves, it stores what/why/outcome
and distils a one-line **lesson**, recalled before the next decision on that
symbol. A transparent, offline stand-in for a vector store.

### Phase 6 — Orchestration (`orchestration/`)
* `graph.py` — a tiny dependency-graph engine (à la LangGraph) that resolves a
  topological order and threads shared state. Detects cycles & missing deps.
* `pipeline.py` — wires the agents into the graph and exposes `analyze()`.

### Phase 7 — Backtesting (`backtest/`)
* `portfolio.py` — cash + positions, target-weight rebalancing with commissions
  and stop/target exits.
* `engine.py` — **walk-forward** simulation that only ever shows a strategy the
  history available up to each decision date (**no look-ahead**).
* `metrics.py` — total return, CAGR, Sharpe, Sortino, max drawdown, Calmar, win rate.
* `strategies.py` — `AgentStrategy` (the full pipeline) plus `BuyAndHold` and
  `MovingAverageCrossover` baselines.

### Phase 8 — CLI (`cli.py`)
A `typer` + `rich` interface: `analyze`, `backtest`, `config`, `version`.

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

If a live provider is selected but its key is missing, the system **degrades
gracefully** back to offline mode instead of crashing.

---

## Project layout

```
trading_agents/
├── config.py              # settings (pydantic)
├── data/                  # market data + indicators
├── llm/                   # provider-agnostic chat (offline/openai/anthropic)
├── agents/                # analysts, debate, risk, trader + typed schemas
├── memory/                # reflection memory
├── orchestration/         # graph engine + trading pipeline
├── backtest/              # portfolio, engine, metrics, strategies
└── cli.py                 # typer CLI
examples/run_pipeline.py   # end-to-end demo
tests/                     # 36 offline, deterministic tests
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
