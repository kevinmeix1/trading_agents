"""Paper trading demo — runs the full multi-agent pipeline on simulated data."""

from __future__ import annotations

import asyncio
import json

from trading_agents.config import settings
from trading_agents.runner import configure_logging, run_all


def main() -> None:
    configure_logging()
    results = asyncio.run(run_all(settings.symbols))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
