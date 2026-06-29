"""FastAPI application factory and dev runner."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from trading_agents.config import Settings, get_settings
from trading_agents.service import TradingService

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12, examples=["AAPL"])
    lookback_days: int = Field(365, ge=60, le=2000)
    debate_rounds: int = Field(2, ge=1, le=5)
    news: list[str] = Field(default_factory=list)


class BacktestRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12, examples=["MSFT"])
    days: int = Field(500, ge=120, le=3000)
    rebalance_every: int = Field(21, ge=1, le=120)
    strategies: list[str] = Field(default_factory=list)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Raises a helpful error if the optional ``web`` extra is not installed.
    """

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            "FastAPI is not installed. Install the web extra with "
            "`pip install trading-agents[web]`."
        ) from exc

    settings = settings or get_settings()
    service = TradingService(settings)

    app = FastAPI(
        title="trading_agents API",
        version=service.config()["version"],
        description="Multi-agent AI trading research — analyse and backtest over HTTP.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return service.config()

    @app.get("/api/strategies")
    def strategies() -> list[dict[str, str]]:
        return service.available_strategies()

    @app.post("/api/analyze")
    def analyze(req: AnalyzeRequest) -> dict[str, Any]:
        try:
            return service.analyze(
                req.symbol,
                lookback_days=req.lookback_days,
                news=req.news or None,
                debate_rounds=req.debate_rounds,
            )
        except Exception as exc:  # surface a clean 400 instead of a 500 stack
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/backtest")
    def backtest(req: BacktestRequest) -> dict[str, Any]:
        try:
            return service.backtest(
                req.symbol,
                days=req.days,
                rebalance_every=req.rebalance_every,
                strategies=req.strategies or None,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Serve the static dashboard at the root.
    if WEB_DIR.is_dir():
        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


def run(host: str = "127.0.0.1", port: int = 8000, settings: Settings | None = None) -> None:
    """Launch a development server with uvicorn."""

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            "uvicorn is not installed. Install the web extra with "
            "`pip install trading-agents[web]`."
        ) from exc

    uvicorn.run(create_app(settings), host=host, port=port)
