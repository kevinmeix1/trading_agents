"""Market data providers.

Two backends are supported:

* ``synthetic`` - a deterministic geometric-Brownian-motion generator that needs
  no network access. Perfect for tests, demos and CI.
* ``yfinance``  - real historical data (requires the optional ``yfinance`` extra
  and network access).

Both return the same :class:`~trading_agents.data.types.PriceHistory` object so
the rest of the system never needs to know where the data came from.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from trading_agents.config import DataSource, Settings, get_settings
from trading_agents.data.types import PriceHistory


class MarketDataProvider(ABC):
    """Abstract market data source."""

    @abstractmethod
    def history(self, symbol: str, *, lookback_days: int = 365) -> PriceHistory:
        """Return daily OHLCV history for ``symbol``."""


def _seed_for(symbol: str, base_seed: int) -> int:
    """Derive a stable per-symbol seed so each ticker has its own price path."""

    digest = hashlib.sha256(f"{symbol}:{base_seed}".encode()).hexdigest()
    return int(digest[:8], 16)


class SyntheticMarketDataProvider(MarketDataProvider):
    """Generate plausible price series using geometric Brownian motion.

    Each symbol gets a deterministic drift/volatility profile derived from its
    name, so results are reproducible and symbols behave differently.
    """

    def __init__(self, base_seed: int = 42) -> None:
        self.base_seed = base_seed
        self._cache: dict[tuple[str, int], PriceHistory] = {}

    def history(self, symbol: str, *, lookback_days: int = 365) -> PriceHistory:
        key = (symbol.upper(), max(lookback_days, 30))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        rng = np.random.default_rng(_seed_for(symbol, self.base_seed))

        # Per-symbol regime parameters.
        start_price = float(rng.uniform(20, 400))
        annual_drift = float(rng.uniform(-0.05, 0.25))
        annual_vol = float(rng.uniform(0.15, 0.55))

        dt = 1.0 / 252.0
        mu = annual_drift * dt
        sigma = annual_vol * np.sqrt(dt)

        n = max(lookback_days, 30)
        shocks = rng.normal(loc=mu - 0.5 * sigma**2, scale=sigma, size=n)
        log_path = np.cumsum(shocks)
        close = start_price * np.exp(log_path)

        # Build OHLC around the close with a little intraday noise.
        intraday = np.abs(rng.normal(0.0, sigma, size=n))
        high = close * (1 + intraday)
        low = close * (1 - intraday)
        open_ = np.concatenate([[start_price], close[:-1]])
        open_ = np.clip(open_, low, high)
        volume = rng.uniform(1e6, 1e7, size=n).round()

        end = pd.Timestamp.today().normalize()
        index = pd.bdate_range(end=end, periods=n)

        frame = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=index,
        )
        history = PriceHistory(symbol=symbol.upper(), frame=frame)
        self._cache[key] = history
        return history


class YFinanceMarketDataProvider(MarketDataProvider):
    """Real historical data via the optional ``yfinance`` package."""

    def history(self, symbol: str, *, lookback_days: int = 365) -> PriceHistory:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "yfinance is not installed. Install with `pip install trading-agents[data]` "
                "or set TA_DATA_SOURCE=synthetic."
            ) from exc

        period_days = max(lookback_days + 10, 40)
        raw = yf.download(
            symbol,
            period=f"{period_days}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:  # pragma: no cover - network dependent
            raise RuntimeError(f"No data returned for symbol {symbol!r}.")

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        frame = raw.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )[["open", "high", "low", "close", "volume"]]
        return PriceHistory(symbol=symbol.upper(), frame=frame.tail(lookback_days))


def get_market_provider(settings: Settings | None = None) -> MarketDataProvider:
    """Factory that returns the configured market data provider."""

    settings = settings or get_settings()
    if settings.data_source == DataSource.YFINANCE:
        return YFinanceMarketDataProvider()
    return SyntheticMarketDataProvider(base_seed=settings.random_seed)
