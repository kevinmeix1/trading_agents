"""Strategies the backtester can drive.

A strategy maps a *slice* of price history (everything known up to the decision
date) to a :class:`~trading_agents.agents.schemas.TradeDecision`. This is exactly
the contract the multi-agent pipeline already satisfies, so the agents plug
straight into the backtester. Two simple baselines are provided for comparison.
"""

from __future__ import annotations

from typing import Protocol

from trading_agents.agents.schemas import Action, TradeDecision
from trading_agents.data.indicators import annualised_volatility, atr, bollinger, rsi, sma
from trading_agents.data.types import PriceHistory
from trading_agents.orchestration.pipeline import TradingPipeline


class Strategy(Protocol):
    name: str

    def decide(self, history: PriceHistory) -> TradeDecision: ...


def _vol_target_weight(history: PriceHistory, target_vol: float, max_weight: float) -> float:
    """Risk-parity-style weight that scales inversely with realised volatility."""

    vol = annualised_volatility(history.frame["close"])
    if vol <= 1e-6:
        return max_weight
    return float(min(max_weight, target_vol / vol))


def _atr_stops(history: PriceHistory) -> tuple[float, float]:
    """Return ``(stop_loss_pct, take_profit_pct)`` derived from ATR."""

    last_close = float(history.frame["close"].iloc[-1])
    atr_pct = float(atr(history.frame).iloc[-1]) / last_close if last_close else 0.0
    stop = min(0.25, max(0.03, atr_pct * 2.5))
    return stop, min(0.6, stop * 2.0)


class AgentStrategy:
    """Drive the full multi-agent pipeline inside the backtester."""

    name = "multi_agent"

    def __init__(self, pipeline: TradingPipeline):
        self.pipeline = pipeline

    def decide(self, history: PriceHistory) -> TradeDecision:
        return self.pipeline.analyze_history(history).decision


class BuyAndHold:
    name = "buy_and_hold"

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        return TradeDecision(
            symbol=history.symbol,
            action=Action.BUY,
            target_weight=self.weight,
            confidence=1.0,
            rationale="Always fully invested.",
        )


class MovingAverageCrossover:
    """Classic baseline: long when fast SMA > slow SMA, flat otherwise."""

    name = "sma_crossover"

    def __init__(self, fast: int = 20, slow: int = 50, weight: float = 1.0):
        self.fast = fast
        self.slow = slow
        self.weight = weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        close = history.frame["close"]
        fast = float(sma(close, self.fast).iloc[-1])
        slow = float(sma(close, self.slow).iloc[-1])
        if fast > slow:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=self.weight,
                confidence=0.6,
                rationale=f"Fast SMA {fast:.2f} > slow SMA {slow:.2f}.",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.SELL,
            target_weight=0.0,
            confidence=0.6,
            rationale=f"Fast SMA {fast:.2f} <= slow SMA {slow:.2f}.",
        )


class MomentumStrategy:
    """Time-series momentum with volatility-targeted sizing.

    Goes long when trailing ``lookback``-day return is positive, sizing the
    position so its expected volatility matches ``target_vol`` (risk parity for
    a single asset). Exits to cash on negative momentum.
    """

    name = "momentum"

    def __init__(self, lookback: int = 90, target_vol: float = 0.20, max_weight: float = 1.0):
        self.lookback = lookback
        self.target_vol = target_vol
        self.max_weight = max_weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        close = history.frame["close"]
        window = close.tail(self.lookback + 1)
        trailing_return = float(window.iloc[-1] / window.iloc[0] - 1.0) if len(window) > 1 else 0.0
        stop, target = _atr_stops(history)
        if trailing_return > 0:
            weight = _vol_target_weight(history, self.target_vol, self.max_weight)
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=weight,
                confidence=min(1.0, 0.5 + abs(trailing_return)),
                stop_loss_pct=stop,
                take_profit_pct=target,
                rationale=f"{self.lookback}d momentum {trailing_return:+.1%}; vol-targeted size.",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.SELL,
            target_weight=0.0,
            confidence=0.55,
            rationale=f"{self.lookback}d momentum {trailing_return:+.1%}; flat.",
        )


class MeanReversionStrategy:
    """RSI mean-reversion: buy oversold dips, trim into overbought strength."""

    name = "mean_reversion"

    def __init__(self, period: int = 14, oversold: float = 35.0, overbought: float = 65.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def decide(self, history: PriceHistory) -> TradeDecision:
        last_rsi = float(rsi(history.frame["close"], self.period).iloc[-1])
        stop, target = _atr_stops(history)
        if last_rsi <= self.oversold:
            # Deeper oversold => larger position (scaled into the band).
            weight = min(1.0, (self.oversold - last_rsi) / self.oversold + 0.4)
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=round(weight, 4),
                confidence=0.6,
                stop_loss_pct=stop,
                take_profit_pct=target,
                rationale=f"RSI {last_rsi:.0f} oversold; mean-reversion long.",
            )
        if last_rsi >= self.overbought:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.SELL,
                target_weight=0.0,
                confidence=0.6,
                rationale=f"RSI {last_rsi:.0f} overbought; take profit.",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.HOLD,
            target_weight=0.0,
            confidence=0.4,
            rationale=f"RSI {last_rsi:.0f} neutral.",
        )


class BollingerBreakoutStrategy:
    """Trade Bollinger-band breakouts: long on a close above the upper band."""

    name = "bollinger_breakout"

    def __init__(self, window: int = 20, num_std: float = 2.0, max_weight: float = 1.0):
        self.window = window
        self.num_std = num_std
        self.max_weight = max_weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        close = history.frame["close"]
        bands = bollinger(close, self.window, self.num_std)
        price = float(close.iloc[-1])
        upper = float(bands["bb_upper"].iloc[-1])
        lower = float(bands["bb_lower"].iloc[-1])
        mid = float(bands["bb_mid"].iloc[-1])
        stop, target = _atr_stops(history)
        if price >= upper:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=self.max_weight,
                confidence=0.65,
                stop_loss_pct=stop,
                take_profit_pct=target,
                rationale=f"Close {price:.2f} broke upper band {upper:.2f}.",
            )
        if price <= lower or price < mid:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.SELL,
                target_weight=0.0,
                confidence=0.6,
                rationale=f"Close {price:.2f} below mid-band {mid:.2f}.",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.HOLD,
            target_weight=0.0,
            confidence=0.4,
            rationale="Inside Bollinger bands.",
        )


class EnsembleStrategy:
    """Blend several sub-strategies by majority vote, weighted by confidence.

    The ensemble buys when the confidence-weighted vote is net-long, sizing the
    position by agreement strength (and volatility-targeting the result). This
    decorrelates single-signal failure modes — the core idea behind the whole
    multi-agent design, applied to plain technical strategies for comparison.
    """

    name = "ensemble"

    def __init__(
        self,
        members: list[Strategy] | None = None,
        *,
        target_vol: float = 0.20,
        max_weight: float = 1.0,
    ):
        self.members: list[Strategy] = members or [
            MomentumStrategy(),
            MeanReversionStrategy(),
            BollingerBreakoutStrategy(),
            MovingAverageCrossover(),
        ]
        self.target_vol = target_vol
        self.max_weight = max_weight

    def decide(self, history: PriceHistory) -> TradeDecision:
        score = 0.0
        total = 0.0
        reasons: list[str] = []
        for member in self.members:
            d = member.decide(history)
            total += d.confidence
            if d.action == Action.BUY:
                score += d.confidence
            elif d.action == Action.SELL:
                score -= d.confidence
            reasons.append(f"{member.name}:{d.action.value}")

        net = score / total if total else 0.0
        stop, target = _atr_stops(history)
        cap = _vol_target_weight(history, self.target_vol, self.max_weight)
        if net > 0.15:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.BUY,
                target_weight=round(min(cap, abs(net) * cap + 0.2 * cap), 4),
                confidence=round(min(1.0, abs(net) + 0.2), 4),
                stop_loss_pct=stop,
                take_profit_pct=target,
                rationale=f"Ensemble net {net:+.2f} long ({', '.join(reasons)}).",
            )
        if net < -0.15:
            return TradeDecision(
                symbol=history.symbol,
                action=Action.SELL,
                target_weight=0.0,
                confidence=round(min(1.0, abs(net) + 0.2), 4),
                rationale=f"Ensemble net {net:+.2f} short ({', '.join(reasons)}).",
            )
        return TradeDecision(
            symbol=history.symbol,
            action=Action.HOLD,
            target_weight=0.0,
            confidence=0.4,
            rationale=f"Ensemble inconclusive (net {net:+.2f}).",
        )
