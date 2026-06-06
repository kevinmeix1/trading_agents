# Multi-Agent Trading System — Architecture

## Design Philosophy

This system treats trading as a **sequential decision pipeline under hard constraints**, not a single LLM prompt. Agents specialize; a risk veto gate has final authority; every decision is auditable via event sourcing.

## Advanced Patterns Used

| Pattern | Purpose |
|---------|---------|
| **Hierarchical orchestration** | Meta-orchestrator routes work through specialist agents in phases |
| **Blackboard / shared memory** | Agents read/write structured artifacts instead of chat history |
| **Debate + judge consensus** | Bull/bear agents argue; judge synthesizes to reduce single-model bias |
| **Risk veto gate** | Deterministic rules block trades before execution (non-negotiable) |
| **Regime-adaptive routing** | Market regime changes agent weights and which pipeline runs |
| **Event sourcing** | Every agent action emits events for replay, audit, and backtesting |
| **Structured outputs** | Pydantic schemas enforce machine-parseable agent decisions |
| **Tool abstraction layer** | Agents call tools (market data, portfolio) — swappable for live vs paper |

## Pipeline Phases

```
Market Event
     │
     ▼
┌─────────────┐
│   REGIME    │  Detect: trending / mean-reverting / high-vol / crisis
│  DETECTOR   │
└──────┬──────┘
       ▼
┌─────────────┐     parallel
│  ANALYSIS   │ ──► Market Analyst, Sentiment Analyst
│   LAYER     │
└──────┬──────┘
       ▼
┌─────────────┐
│   DEBATE    │ ──► Bull Agent ↔ Bear Agent → Judge Agent
│   LAYER     │
└──────┬──────┘
       ▼
┌─────────────┐
│  PORTFOLIO  │ ──► Position sizing, allocation proposal
│   MANAGER   │
└──────┬──────┘
       ▼
┌─────────────┐
│ RISK VETO   │ ──► Hard constraints (max drawdown, position limits, VaR)
│    GATE     │     CAN BLOCK — no override by LLM agents
└──────┬──────┘
       ▼
┌─────────────┐
│  EXECUTION  │ ──► Order routing (paper or live broker adapter)
│   AGENT     │
└─────────────┘
```

## Agent Responsibilities

### Market Analyst
Technical + fundamental signals. Outputs `MarketAnalysis` with direction, confidence, key levels.

### Sentiment Analyst
News/social sentiment aggregation. Outputs `SentimentReport`.

### Bull / Bear / Judge (Debate Layer)
- **Bull**: strongest long case from available evidence
- **Bear**: strongest short/skip case
- **Judge**: weighted synthesis → `DebateVerdict` with action bias

### Portfolio Manager
Translates verdict into concrete `TradeProposal` (symbol, side, quantity, rationale).

### Risk Manager (Veto Gate)
Deterministic checks: position limits, sector concentration, max daily loss, leverage caps.

### Execution Agent
Idempotent order submission with slippage modeling in paper mode.

## Memory Tiers

1. **Working memory** — current pipeline run (blackboard)
2. **Episodic memory** — past trades + outcomes for agent context
3. **Semantic memory** (Phase 3) — vector store of market narratives, earnings summaries

## Roadmap

### Phase 1 — Foundation (this PR)
- Core orchestrator, blackboard, event bus
- All agent interfaces + mock LLM implementations
- Risk veto gate with configurable constraints
- Paper trading example

### Phase 2 — LLM Integration
- OpenAI / Anthropic adapters with structured output
- Real market data (Alpaca, Polygon, yfinance)
- LangGraph state machine for complex branching

### Phase 3 — Production Hardening
- Vector memory (Chroma/Pinecone)
- Live broker adapters (IBKR, Alpaca)
- Backtesting harness with event replay
- Human-in-the-loop approval for large orders
- Monitoring (Prometheus, structured logging)

### Phase 4 — Advanced Alpha
- Reinforcement learning agent for execution timing
- Cross-asset correlation agent
- Options / derivatives specialist agents
- Ensemble model routing by regime

## Safety Defaults

- **Paper trading only** until explicitly configured
- Risk gate **cannot be disabled** in production config
- All LLM outputs validated against schemas before acting
- Maximum order size capped at config level
