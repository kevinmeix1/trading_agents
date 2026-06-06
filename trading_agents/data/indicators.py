"""Technical indicators and a compact feature snapshot for agents.

Everything is implemented with ``pandas``/``numpy`` only, so there is no
dependency on TA-Lib or other native libraries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from trading_agents.data.types import PriceHistory


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
    pct_from_sma50: float
    annualised_vol: float
    trend: str  # "uptrend" | "downtrend" | "sideways"
    momentum: str  # "overbought" | "oversold" | "neutral"

    def to_dict(self) -> dict:
        return asdict(self)


def compute_indicators(history: PriceHistory) -> IndicatorSnapshot:
    """Compute a full :class:`IndicatorSnapshot` from a price history."""

    close = history.frame["close"]
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    ema12 = ema(close, 12)
    rsi14 = rsi(close, 14)
    macd_df = macd(close)
    bb = bollinger(close)

    last_close = float(close.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])
    pct_from_sma50 = (last_close - last_sma50) / last_sma50 * 100 if last_sma50 else 0.0

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
        bb_upper=round(float(bb["bb_upper"].iloc[-1]), 4),
        bb_lower=round(float(bb["bb_lower"].iloc[-1]), 4),
        pct_from_sma50=round(pct_from_sma50, 2),
        annualised_vol=round(annualised_volatility(close), 4),
        trend=trend,
        momentum=momentum,
    )
