"""Analyst agents.

Each analyst examines one "lens" on the asset and emits an
:class:`~trading_agents.agents.schemas.AnalystReport` with a signal in
``[-1, 1]`` plus a confidence and rationale.

* :class:`TechnicalAnalyst`   - price action & momentum indicators
* :class:`FundamentalAnalyst` - valuation & quality (pseudo-fundamentals offline)
* :class:`SentimentAnalyst`   - news / headline tone
* :class:`MacroAnalyst`       - regime & volatility backdrop
"""

from __future__ import annotations

import hashlib
from typing import Any

from trading_agents.agents.base import AgentContext, BaseAgent
from trading_agents.agents.schemas import AnalystReport


def _stable_unit(*parts: str) -> float:
    """Deterministic float in [0, 1) derived from the given strings."""

    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class _AnalystBase(BaseAgent):
    """Shared analyst plumbing: run heuristics/LLM then validate to a model."""

    def analyze(self, ctx: AgentContext) -> AnalystReport:
        data = self.reason(ctx)
        report = AnalystReport(
            agent=self.role,
            signal=_clamp(float(data["signal"])),
            confidence=max(0.0, min(1.0, float(data["confidence"]))),
            rationale=str(data["rationale"]),
            key_points=list(data.get("key_points", [])),
        )
        ctx.remember(self.role, report)
        self.log(f"signal={report.signal:+.2f} ({report.stance}) conf={report.confidence:.2f}")
        return report


class TechnicalAnalyst(_AnalystBase):
    role = "technical_analyst"

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        ind = ctx.indicators
        signal = 0.0
        points: list[str] = []

        if ind.trend == "uptrend":
            signal += 0.35
            points.append("Price in an uptrend (SMA20 > SMA50).")
        elif ind.trend == "downtrend":
            signal -= 0.35
            points.append("Price in a downtrend (SMA20 < SMA50).")

        if ind.macd_hist > 0:
            signal += 0.2
            points.append("MACD histogram positive (bullish momentum).")
        else:
            signal -= 0.2
            points.append("MACD histogram negative (bearish momentum).")

        # RSI: fade extremes (mean-reversion bias).
        if ind.momentum == "overbought":
            signal -= 0.2
            points.append(f"RSI {ind.rsi_14} overbought; pullback risk.")
        elif ind.momentum == "oversold":
            signal += 0.2
            points.append(f"RSI {ind.rsi_14} oversold; bounce potential.")

        signal += _clamp(ind.pct_from_sma50 / 100.0, -0.15, 0.15)

        confidence = min(0.9, 0.45 + abs(signal) / 2)
        rationale = (
            f"{ind.symbol}: {ind.trend}, RSI {ind.rsi_14}, MACD hist {ind.macd_hist}, "
            f"{ind.pct_from_sma50:+.1f}% vs SMA50."
        )
        return {
            "signal": _clamp(signal),
            "confidence": confidence,
            "rationale": rationale,
            "key_points": points,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        ind = ctx.indicators
        system = (
            "You are a disciplined technical analyst. Judge the chart objectively "
            "using trend, momentum and mean-reversion. Output a signal in [-1,1] "
            "(negative=bearish, positive=bullish), a confidence in [0,1], a short "
            "rationale and key_points (list of strings)."
        )
        user = (
            f"Symbol: {ind.symbol}\nlast_close: {ind.last_close}\ntrend: {ind.trend}\n"
            f"sma_20: {ind.sma_20}\nsma_50: {ind.sma_50}\nrsi_14: {ind.rsi_14}\n"
            f"macd_hist: {ind.macd_hist}\npct_from_sma50: {ind.pct_from_sma50}\n"
            f"annualised_vol: {ind.annualised_vol}\nmomentum: {ind.momentum}"
        )
        return system, user


class FundamentalAnalyst(_AnalystBase):
    role = "fundamental_analyst"

    def _pseudo_fundamentals(self, symbol: str) -> dict[str, float]:
        """Deterministic stand-in fundamentals when no real data is available."""

        pe = 8 + _stable_unit(symbol, "pe") * 45  # 8..53
        rev_growth = (_stable_unit(symbol, "growth") - 0.3) * 0.6  # -18%..+18%
        margin = _stable_unit(symbol, "margin") * 0.35  # 0..35%
        debt_to_equity = _stable_unit(symbol, "de") * 2.5  # 0..2.5
        return {
            "pe": round(pe, 1),
            "rev_growth": round(rev_growth, 3),
            "margin": round(margin, 3),
            "debt_to_equity": round(debt_to_equity, 2),
        }

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        f = ctx.scratchpad.get("fundamentals") or self._pseudo_fundamentals(ctx.symbol)
        ctx.remember("fundamentals", f)
        signal = 0.0
        points: list[str] = []

        if f["pe"] < 18:
            signal += 0.25
            points.append(f"Attractive valuation (P/E {f['pe']}).")
        elif f["pe"] > 35:
            signal -= 0.25
            points.append(f"Rich valuation (P/E {f['pe']}).")

        signal += _clamp(f["rev_growth"] * 3, -0.3, 0.3)
        points.append(f"Revenue growth {f['rev_growth'] * 100:+.1f}%.")

        signal += _clamp((f["margin"] - 0.15) * 2, -0.2, 0.2)
        points.append(f"Net margin {f['margin'] * 100:.1f}%.")

        if f["debt_to_equity"] > 1.5:
            signal -= 0.15
            points.append(f"Elevated leverage (D/E {f['debt_to_equity']}).")

        confidence = 0.5 + abs(signal) / 3
        rationale = (
            f"P/E {f['pe']}, growth {f['rev_growth'] * 100:+.1f}%, "
            f"margin {f['margin'] * 100:.1f}%, D/E {f['debt_to_equity']}."
        )
        return {
            "signal": _clamp(signal),
            "confidence": min(0.9, confidence),
            "rationale": rationale,
            "key_points": points,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        f = ctx.scratchpad.get("fundamentals", {})
        system = (
            "You are a value-oriented fundamental analyst. Weigh valuation, growth, "
            "profitability and balance-sheet risk. Output signal [-1,1], confidence "
            "[0,1], rationale and key_points."
        )
        user = "\n".join(f"{k}: {v}" for k, v in f.items()) or f"Symbol: {ctx.symbol}"
        return system, user


class SentimentAnalyst(_AnalystBase):
    role = "sentiment_analyst"

    _POS = {"beat", "surge", "growth", "upgrade", "record", "strong", "bullish", "win", "soar"}
    _NEG = {"miss", "fall", "downgrade", "lawsuit", "probe", "weak", "bearish", "cut", "plunge"}

    def _score_headlines(self, news: list[str]) -> tuple[float, list[str]]:
        score = 0
        hits: list[str] = []
        for headline in news:
            words = {w.strip(".,!?").lower() for w in headline.split()}
            pos = len(words & self._POS)
            neg = len(words & self._NEG)
            if pos or neg:
                hits.append(headline)
            score += pos - neg
        norm = _clamp(score / max(3, len(news)))
        return norm, hits[:4]

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        if ctx.news:
            signal, hits = self._score_headlines(ctx.news)
            points = [f"Headline tone: {h}" for h in hits] or ["Mixed/neutral headlines."]
            rationale = f"Scored {len(ctx.news)} headlines; net tone {signal:+.2f}."
        else:
            # No live feed: use a price-confirmed sentiment proxy. The static
            # per-symbol tilt is intentionally small so it cannot pin a name
            # permanently bullish/bearish; recent trend dominates and so the
            # proxy adapts as we walk forward in a backtest.
            base = (_stable_unit(ctx.symbol, "sent") - 0.5) * 0.4
            drift = _clamp(ctx.indicators.pct_from_sma50 / 60.0, -0.5, 0.5)
            signal = _clamp(base * 0.3 + drift * 0.7)
            points = ["No live headlines; using price-confirmed sentiment proxy."]
            rationale = f"Proxy sentiment {signal:+.2f} (no live news feed)."
        return {
            "signal": signal,
            "confidence": 0.4 + abs(signal) / 3,
            "rationale": rationale,
            "key_points": points,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        system = (
            "You are a market sentiment analyst. Gauge the tone of news and crowd "
            "positioning. Output signal [-1,1], confidence [0,1], rationale, key_points."
        )
        headlines = "\n".join(f"- {h}" for h in ctx.news) or "(no live headlines)"
        user = f"Symbol: {ctx.symbol}\nHeadlines:\n{headlines}"
        return system, user


class FlowAnalyst(_AnalystBase):
    """Volume / money-flow analyst.

    Reads order-flow proxies — On-Balance-Volume trend, the relative volume
    surge, and the position within the Bollinger band — to judge whether price
    moves are *confirmed* by participation (smart-money accumulation) or are
    thin and prone to reversal.
    """

    role = "flow_analyst"

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        ind = ctx.indicators
        signal = 0.0
        points: list[str] = []

        if ind.obv_trend == "accumulation":
            signal += 0.3
            points.append("On-balance volume rising (accumulation).")
        elif ind.obv_trend == "distribution":
            signal -= 0.3
            points.append("On-balance volume falling (distribution).")

        # A volume surge amplifies the prevailing trend's conviction.
        if ind.volume_ratio > 1.3:
            tilt = 0.2 if ind.trend == "uptrend" else -0.2 if ind.trend == "downtrend" else 0.0
            signal += tilt
            points.append(f"Volume surge x{ind.volume_ratio:.2f} confirming {ind.trend}.")
        elif ind.volume_ratio < 0.7:
            signal *= 0.6
            points.append("Thin volume; fade conviction.")

        # Extreme band position is a mean-reversion warning.
        if ind.bb_pct > 0.95:
            signal -= 0.15
            points.append("Price pinned to upper band; stretched.")
        elif ind.bb_pct < 0.05:
            signal += 0.15
            points.append("Price pinned to lower band; washed out.")

        confidence = min(0.85, 0.4 + abs(signal) / 2)
        rationale = (
            f"OBV {ind.obv_trend}, rel-volume x{ind.volume_ratio:.2f}, "
            f"band position {ind.bb_pct:.0%}."
        )
        return {
            "signal": _clamp(signal),
            "confidence": confidence,
            "rationale": rationale,
            "key_points": points,
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        ind = ctx.indicators
        system = (
            "You are a volume / order-flow analyst. Decide whether price action is "
            "confirmed by participation or likely to reverse. Output signal [-1,1], "
            "confidence [0,1], rationale, key_points."
        )
        user = (
            f"Symbol: {ind.symbol}\nobv_trend: {ind.obv_trend}\n"
            f"volume_ratio: {ind.volume_ratio}\nbb_pct: {ind.bb_pct}\ntrend: {ind.trend}"
        )
        return system, user


class MacroAnalyst(_AnalystBase):
    role = "macro_analyst"

    def heuristic(self, ctx: AgentContext) -> dict[str, Any]:
        vol = ctx.indicators.annualised_vol
        # High volatility => risk-off tilt; calm trending tape => risk-on.
        if vol > 0.45:
            regime = "risk-off (high volatility)"
            signal = -0.25
        elif vol < 0.25 and ctx.indicators.trend == "uptrend":
            regime = "risk-on (calm uptrend)"
            signal = 0.25
        else:
            regime = "neutral"
            signal = 0.05 if ctx.indicators.trend == "uptrend" else -0.05

        # A small deterministic macro backdrop component per symbol/sector proxy.
        signal += (_stable_unit(ctx.symbol, "macro") - 0.5) * 0.2
        return {
            "signal": _clamp(signal),
            "confidence": 0.5,
            "rationale": f"Regime: {regime}; annualised vol {vol:.2f}.",
            "key_points": [f"Volatility regime: {regime}."],
        }

    def prompt(self, ctx: AgentContext) -> tuple[str, str]:
        system = (
            "You are a macro strategist. Assess the volatility regime and broad "
            "risk appetite. Output signal [-1,1], confidence [0,1], rationale, key_points."
        )
        user = (
            f"Symbol: {ctx.symbol}\nannualised_vol: {ctx.indicators.annualised_vol}\n"
            f"trend: {ctx.indicators.trend}"
        )
        return system, user
