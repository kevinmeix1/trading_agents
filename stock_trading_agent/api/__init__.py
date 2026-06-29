"""HTTP API for stock_trading_agent (FastAPI).

The web layer is intentionally thin: it validates requests, delegates to
:class:`stock_trading_agent.service.TradingService`, and serves the static dashboard.
FastAPI is imported lazily inside :func:`create_app` so the core package keeps
working without the optional ``web`` extra installed.
"""

from stock_trading_agent.api.server import create_app, run

__all__ = ["create_app", "run"]
