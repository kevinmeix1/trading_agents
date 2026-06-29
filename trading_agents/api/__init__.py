"""HTTP API for trading_agents (FastAPI).

The web layer is intentionally thin: it validates requests, delegates to
:class:`trading_agents.service.TradingService`, and serves the static dashboard.
FastAPI is imported lazily inside :func:`create_app` so the core package keeps
working without the optional ``web`` extra installed.
"""

from trading_agents.api.server import create_app, run

__all__ = ["create_app", "run"]
