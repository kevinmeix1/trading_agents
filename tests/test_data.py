from __future__ import annotations

from trading_agents.data.indicators import compute_indicators, rsi
from trading_agents.data.market import SyntheticMarketDataProvider
from trading_agents.data.types import PriceHistory


def test_synthetic_is_deterministic():
    a = SyntheticMarketDataProvider(base_seed=7).history("AAPL", lookback_days=120)
    b = SyntheticMarketDataProvider(base_seed=7).history("AAPL", lookback_days=120)
    assert a.frame["close"].tolist() == b.frame["close"].tolist()


def test_symbols_differ():
    p = SyntheticMarketDataProvider(base_seed=7)
    aapl = p.history("AAPL", lookback_days=120).latest_close
    msft = p.history("MSFT", lookback_days=120).latest_close
    assert aapl != msft


def test_history_columns_and_ohlc_consistency(history):
    for col in ("open", "high", "low", "close", "volume"):
        assert col in history.frame.columns
    assert (history.frame["high"] >= history.frame["low"]).all()
    assert (history.frame["high"] >= history.frame["close"]).all()
    assert (history.frame["low"] <= history.frame["close"]).all()


def test_price_history_validates_columns():
    import pandas as pd
    import pytest

    bad = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(ValueError):
        PriceHistory(symbol="X", frame=bad)


def test_rsi_bounds(history):
    values = rsi(history.frame["close"])
    assert values.min() >= 0
    assert values.max() <= 100


def test_indicator_snapshot_fields(history):
    snap = compute_indicators(history)
    assert snap.symbol == "AAPL"
    assert snap.trend in {"uptrend", "downtrend", "sideways"}
    assert snap.momentum in {"overbought", "oversold", "neutral"}
    assert 0 <= snap.rsi_14 <= 100
