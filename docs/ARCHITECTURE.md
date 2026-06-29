# stock_trading_agent — Architecture

> Educational / research project. Nothing here is investment advice. Default
> data is synthetic and the system runs fully offline and deterministically.

## 1. Overview

`stock_trading_agent` decomposes the question *"should I trade this asset?"* the way a
real investment desk does: a team of specialised agents independently analyse an
asset, two researchers **debate** the bull and bear cases, a **risk** officer
sizes the position under a hard mandate, and a **portfolio manager** issues the
final, actionable decision. The same decision function plugs straight into a
walk-forward **backtester** so strategies can be evaluated honestly against
baselines.

The system is built in clean, composable layers. Every layer has a small, typed
contract, so each one is independently testable and replaceable.

## 2. Layered architecture

| Layer | Package | Responsibility |
|---|---|---|
| Configuration | `config.py` | Typed settings from env / `.env` (pydantic) |
| Data | `data/` | Market data providers + technical indicators |
| LLM abstraction | `llm/` | Provider-agnostic chat with offline fallback |
| Agents | `agents/` | Analysts, debate, risk, portfolio manager |
| Memory | `memory/` | File-backed reflection memory (lessons) |
| Orchestration | `orchestration/` | DAG engine + end-to-end pipeline |
| Backtest | `backtest/` | Portfolio, walk-forward engine, metrics, strategies |
| Service | `service.py` | Framework-agnostic facade (JSON-ready results) |
| Interfaces | `cli.py`, `api/`, `web/` | Terminal CLI, REST API, web dashboard |

The **service layer** is the seam between business logic and transport: both the
CLI and the HTTP API call `TradingService`, so logic lives in exactly one place.

## 3. Decision pipeline (data flow)

```
            ┌── Technical ─┐
            ├── Fundamental ┤
 Market ───▶├── Sentiment   ├──▶ Debate ──▶ Risk ──▶ Portfolio ──▶ Decision
  Data      ├── Macro       │   (bull vs    (vol-     Manager      (BUY/SELL/
            └── Flow ───────┘    bear +      target +  (final        HOLD)
                                 judge)      Kelly)    authority)
                                                          │
                                                          ▼
                                                  Reflection memory
```

1. **Data** — a `MarketDataProvider` returns an OHLCV `PriceHistory`; indicators
   collapse it into a compact `IndicatorSnapshot` (trend, momentum, volatility,
   ATR, OBV/flow, Bollinger position).
2. **Analysts** — five agents each emit a signal in `[-1, 1]` with a confidence.
   They are mutually independent and run **concurrently**.
3. **Debate** — bull and bear researchers argue from the analyst evidence over
   N rounds; a judge produces a net *conviction* (confidence-weighted, shrunk by
   disagreement).
4. **Risk** — converts conviction + volatility into a position using a blend of
   volatility targeting and **fractional Kelly**, with ATR-based stops, and may
   **veto** the trade.
5. **Portfolio manager** — issues the final `TradeDecision`, bound by the risk
   mandate (it cannot override a veto).
6. **Memory** — resolved trades and their lessons are recalled on the next pass.

## 4. Orchestration engine

`orchestration/graph.py` is a tiny dependency-graph (DAG) engine. Nodes declare
explicit dependencies; the engine validates the graph (detecting cycles and
missing deps), computes dependency **levels**, and executes each level — running
mutually-independent nodes (e.g. the five analysts) concurrently on a thread
pool. Updates are merged back into shared state in a stable, name-sorted order,
so a parallel run is bit-for-bit identical to a sequential one.

## 5. LLM abstraction & determinism

Every agent first computes a complete **heuristic** decision from the data; the
LLM is then asked to *improve* it. Offline (the default), the heuristic *is* the
decision, so the whole system is reproducible and CI-friendly with **no API
key**. Selecting OpenAI/Anthropic is a configuration change only, and a missing
key degrades gracefully back to offline mode instead of crashing.

## 6. Backtesting

The engine steps day by day. On rebalance days it shows a strategy only the
history available up to that date (**no look-ahead**), applies the decision as a
target weight, and every day marks to market and checks stop-loss / take-profit.
Metrics include total return, CAGR, Sharpe, Sortino, max drawdown, Calmar and
win rate. Strategies include the full agent pipeline plus momentum,
mean-reversion, Bollinger breakout, a confidence-weighted ensemble, SMA
crossover and buy-and-hold baselines.

## 7. Interfaces

* **CLI** (`stock-trading-agent`): `analyze`, `backtest`, `serve`, `config`, `version`.
* **REST API** (`api/`): FastAPI app with typed request models.
* **Web dashboard** (`web/`): a buildless single-page app (vanilla JS +
  Chart.js) for interactive analysis and backtesting.

## 8. Extensibility

New analysts implement `BaseAgent` (a `heuristic` + a `prompt`). New strategies
implement the `Strategy` protocol (`decide(history) -> TradeDecision`). New data
or LLM providers implement their respective interfaces. Nothing downstream needs
to change.
