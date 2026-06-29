from __future__ import annotations

import pytest

from stock_trading_agent.config import Settings
from stock_trading_agent.data.market import SyntheticMarketDataProvider


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(verbose=False, memory_path=str(tmp_path / "memory.json"))


@pytest.fixture
def provider() -> SyntheticMarketDataProvider:
    return SyntheticMarketDataProvider(base_seed=42)


@pytest.fixture
def history(provider):
    return provider.history("AAPL", lookback_days=250)
