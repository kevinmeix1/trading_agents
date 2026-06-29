"""Technical indicators and a compact feature snapshot for agents.

Everything is implemented with ``pandas``/``numpy`` only, so there is no
dependency on TA-Lib or other native libraries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from stock_trading_agent.data.types import PriceHistory


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": histogram})


def bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=1).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower})


def annualised_volatility(series: pd.Series, window: int = 20) -> float:
    daily = series.pct_change().dropna().tail(window)
    if daily.empty:
        return 0.0
    return float(daily.std(ddof=0) * np.sqrt(252))


def atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range — a volatility measure used for adaptive stops."""

    high, low, close = frame["high"], frame["low"], frame["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / window, adjust=False).mean()


def on_balance_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — cumulative volume signed by daily price direction."""

    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum()


@dataclass
class IndicatorSnapshot:
    """A compact, human-readable summary of the latest technical state.

    This is what we feed to the analyst agents instead of a giant raw frame.
    """

    symbol: str
    last_close: float
    sma_20: float
    sma_50: float
    ema_12: float
    rsi_14: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_upper: float
    bb_lower: float
    bb_pct: float  # position within the Bollinger band, 0=lower .. 1=upper
    pct_from_sma50: float
    annualised_vol: float
    atr_pct: float  # ATR as a fraction of price (adaptive stop width)
    volume_ratio: float  # recent volume vs. its longer-run average
    obv_trend: str  # "accumulation" | "distribution" | "flat"
    trend: str  # "uptrend" | "downtrend" | "sideways"
    momentum: str  # "overbought" | "oversold" | "neutral"

    def to_dict(self) -> dict:
        return asdict(self)


def compute_indicators(history: PriceHistory) -> IndicatorSnapshot:
    """Compute a full :class:`IndicatorSnapshot` from a price history."""

    frame = history.frame
    close = frame["close"]
    volume = frame["volume"]
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    ema12 = ema(close, 12)
    rsi14 = rsi(close, 14)
    macd_df = macd(close)
    bb = bollinger(close)

    last_close = float(close.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])
    pct_from_sma50 = (last_close - last_sma50) / last_sma50 * 100 if last_sma50 else 0.0

    bb_upper = float(bb["bb_upper"].iloc[-1])
    bb_lower = float(bb["bb_lower"].iloc[-1])
    band = bb_upper - bb_lower
    bb_pct = (last_close - bb_lower) / band if band > 1e-9 else 0.5

    atr_series = atr(frame)
    atr_pct = float(atr_series.iloc[-1]) / last_close if last_close else 0.0

    recent_vol = float(volume.tail(10).mean())
    base_vol = float(volume.tail(50).mean()) or 1.0
    volume_ratio = recent_vol / base_vol if base_vol else 1.0

    obv = on_balance_volume(close, volume)
    obv_slope = float(obv.iloc[-1] - obv.iloc[max(0, len(obv) - 20)])
    if obv_slope > 0:
        obv_trend = "accumulation"
    elif obv_slope < 0:
        obv_trend = "distribution"
    else:
        obv_trend = "flat"

    if float(sma20.iloc[-1]) > last_sma50 * 1.01:
        trend = "uptrend"
    elif float(sma20.iloc[-1]) < last_sma50 * 0.99:
        trend = "downtrend"
    else:
        trend = "sideways"

    last_rsi = float(rsi14.iloc[-1])
    if last_rsi >= 70:
        momentum = "overbought"
    elif last_rsi <= 30:
        momentum = "oversold"
    else:
        momentum = "neutral"

    return IndicatorSnapshot(
        symbol=history.symbol,
        last_close=round(last_close, 4),
        sma_20=round(float(sma20.iloc[-1]), 4),
        sma_50=round(last_sma50, 4),
        ema_12=round(float(ema12.iloc[-1]), 4),
        rsi_14=round(last_rsi, 2),
        macd=round(float(macd_df["macd"].iloc[-1]), 4),
        macd_signal=round(float(macd_df["signal"].iloc[-1]), 4),
        macd_hist=round(float(macd_df["hist"].iloc[-1]), 4),
        bb_upper=round(bb_upper, 4),
        bb_lower=round(bb_lower, 4),
        bb_pct=round(bb_pct, 4),
        pct_from_sma50=round(pct_from_sma50, 2),
        annualised_vol=round(annualised_volatility(close), 4),
        atr_pct=round(atr_pct, 4),
        volume_ratio=round(volume_ratio, 3),
        obv_trend=obv_trend,
        trend=trend,
        momentum=momentum,
    )
