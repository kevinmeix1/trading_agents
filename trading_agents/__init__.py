"""trading_agents: an advanced multi-agent AI system for financial trading.

The package is organised into composable layers:

* ``data``          - market data providers and technical indicators
* ``llm``           - a provider-agnostic chat interface (offline / OpenAI / Anthropic)
* ``agents``        - specialised reasoning agents (analysts, researchers, risk, trader)
* ``memory``        - reflection memory that lets agents learn from past trades
* ``orchestration`` - a small graph engine plus the end-to-end trading pipeline
* ``backtest``      - a vectorised-friendly event backtester and portfolio model

See the project README for a guided, step-by-step tour.
"""

from trading_agents.config import Settings, get_settings

__version__ = "0.1.0"

__all__ = ["Settings", "get_settings", "__version__"]
