# Trading Agents

Multi-agent AI system for financial trading with hierarchical orchestration, debate-based consensus, and a deterministic risk veto gate.

## Architecture

```
Market Event → Regime Detection → Parallel Analysis → Bull/Bear Debate → Judge
    → Portfolio Manager → Risk Veto Gate → Execution
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design, roadmap, and advanced patterns.

## Quick Start

```bash
pip install -e ".[dev]"
python examples/run_paper_trading.py SPY AAPL
# or
trading-agents SPY QQQ
pytest
```

## Step-by-Step Build Guide

### Step 1 — Foundation (done in this repo)

- **Orchestrator** runs agents in strict phases with event sourcing
- **Blackboard** shared memory so agents exchange structured artifacts
- **Debate layer** (bull / bear / judge) reduces single-model bias
- **Risk veto gate** enforces hard limits before any order
- **Paper trading** with simulated market data

### Step 2 — Connect Real LLMs

Replace mock/rule-based logic with structured LLM outputs:

```python
# pip install -e ".[llm]"
from openai import AsyncOpenAI

class LLMMarketAnalyst(MarketAnalyst):
    async def analyze(self, ctx):
        response = await client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format=MarketAnalysis,
        )
        return response.choices[0].message.parsed
```

Wire the same pattern for sentiment, bull, bear, and judge agents. Keep the risk gate **deterministic** — never let the LLM override it.

### Step 3 — Real Market Data

Implement `MarketDataProvider` for your broker/data vendor:

```python
class AlpacaMarketData(MarketDataProvider):
    async def get_snapshot(self, symbol): ...
    async def get_bars(self, symbol, limit): ...
```

Swap `SimulatedMarketData` in `build_orchestrator()`.

### Step 4 — LangGraph State Machine

For branching pipelines (e.g., skip debate in crisis regime):

```python
# pip install -e ".[langgraph]"
from langgraph.graph import StateGraph
```

Map each orchestrator phase to a graph node with conditional edges on `ctx.regime`.

### Step 5 — Production

- Vector memory (Chroma) for earnings/news context
- Human-in-the-loop approval for orders above a threshold
- Backtesting via event replay from `EventBus.history()`
- Live broker adapter behind `ExecutionAgent`

## Configuration

Environment variables (prefix `TRADING_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `TRADING_SYMBOLS` | `SPY,QQQ,AAPL` | Watchlist |
| `TRADING_RISK__MAX_POSITION_PCT` | `0.05` | Max position size |
| `TRADING_RISK__MAX_DAILY_LOSS_PCT` | `0.02` | Daily circuit breaker |
| `TRADING_RISK__MIN_CONFIDENCE` | `0.55` | Min confidence to trade |

## Safety

- Defaults to **paper trading only**
- Risk veto gate cannot be bypassed by LLM agents
- All agent outputs validated with Pydantic schemas
- Full audit trail via event bus

## Project Structure

```
src/trading_agents/
├── core/           # Orchestrator, blackboard, events
├── agents/         # Specialist agents + debate layer
├── regime/         # Market regime detection
├── risk/           # (via execution_agent RiskVetoGate)
├── memory/         # Episodic trade memory
├── tools/          # Market data abstraction
└── bootstrap.py    # Factory wiring
```

## License

MIT
