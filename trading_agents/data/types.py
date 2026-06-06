"""Core market data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class OHLCV:
    """A single Open/High/Low/Close/Volume bar."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class PriceHistory:
    """A symbol's price history wrapped around a tidy ``pandas`` frame.

    The frame is indexed by date and always contains the columns
    ``open, high, low, close, volume``.
    """

    symbol: str
    frame: pd.DataFrame

    def __post_init__(self) -> None:
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(self.frame.columns)
        if missing:
            raise ValueError(f"PriceHistory for {self.symbol} missing columns: {sorted(missing)}")
        if not isinstance(self.frame.index, pd.DatetimeIndex):
            self.frame.index = pd.to_datetime(self.frame.index)
        self.frame = self.frame.sort_index()

    def __len__(self) -> int:
        return len(self.frame)

    @property
    def latest_close(self) -> float:
        return float(self.frame["close"].iloc[-1])

    @property
    def start(self) -> pd.Timestamp:
        return self.frame.index[0]

    @property
    def end(self) -> pd.Timestamp:
        return self.frame.index[-1]

    def window(self, lookback: int) -> pd.DataFrame:
        """Return the trailing ``lookback`` rows."""

        return self.frame.tail(lookback)

    def returns(self) -> pd.Series:
        """Simple daily returns of the close price."""

        return self.frame["close"].pct_change().dropna()
