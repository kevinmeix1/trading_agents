from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from trading_agents.schemas import MarketSnapshot


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_snapshot(self, symbol: str) -> MarketSnapshot:
        ...

    @abstractmethod
    async def get_bars(self, symbol: str, limit: int = 60) -> list[dict]:
        ...


class SimulatedMarketData(MarketDataProvider):
    """
    Deterministic simulated market data for paper trading and tests.

    Uses symbol-seeded random walk so runs are reproducible.
    """

    def __init__(self, base_prices: dict[str, float] | None = None) -> None:
        self.base_prices = base_prices or {
            "SPY": 520.0,
            "QQQ": 440.0,
            "AAPL": 190.0,
            "MSFT": 420.0,
            "NVDA": 900.0,
        }

    def _seed(self, symbol: str) -> random.Random:
        return random.Random(sum(ord(c) for c in symbol))

    async def get_snapshot(self, symbol: str) -> MarketSnapshot:
        bars = await self.get_bars(symbol, limit=2)
        price = bars[-1]["close"]
        spread = price * 0.0002
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            volume=bars[-1]["volume"],
            bid=round(price - spread, 4),
            ask=round(price + spread, 4),
        )

    async def get_bars(self, symbol: str, limit: int = 60) -> list[dict]:
        rng = self._seed(symbol)
        base = self.base_prices.get(symbol, 100.0)
        price = base
        bars: list[dict] = []
        now = datetime.now(timezone.utc)

        for i in range(limit):
            drift = 0.0003 if symbol in ("SPY", "QQQ") else 0.0005
            shock = rng.gauss(0, 0.012)
            price *= 1 + drift + shock
            ts = now - timedelta(minutes=(limit - i) * 15)
            bars.append(
                {
                    "timestamp": ts.isoformat(),
                    "open": round(price * 0.999, 4),
                    "high": round(price * 1.002, 4),
                    "low": round(price * 0.998, 4),
                    "close": round(price, 4),
                    "volume": rng.randint(100_000, 5_000_000),
                }
            )
        return bars
