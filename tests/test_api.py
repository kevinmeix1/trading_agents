from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from stock_trading_agent.api import create_app  # noqa: E402
from stock_trading_agent.service import TradingService  # noqa: E402


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_config_endpoint(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    body = res.json()
    assert body["offline"] is True
    assert "max_workers" in body


def test_strategies_endpoint(client):
    res = client.get("/api/strategies")
    names = {s["name"] for s in res.json()}
    assert {"multi_agent", "ensemble", "buy_and_hold"} <= names


def test_analyze_endpoint(client):
    res = client.post("/api/analyze", json={"symbol": "AAPL", "lookback_days": 200})
    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "AAPL"
    assert body["decision"]["action"] in {"BUY", "SELL", "HOLD"}
    assert len(body["reports"]) == 5
    assert body["debate"] is not None


def test_backtest_endpoint(client):
    res = client.post(
        "/api/backtest",
        json={"symbol": "MSFT", "days": 220, "strategies": ["buy_and_hold", "momentum"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 2
    for r in body["results"]:
        assert "total_return" in r["metrics"]
        assert len(r["equity_curve"]) > 0


def test_service_analyze_is_serialisable(settings):
    svc = TradingService(settings)
    out = svc.analyze("TSLA", lookback_days=180)
    import json

    json.dumps(out)  # must not raise
    assert out["decision"]["symbol"] == "TSLA"
