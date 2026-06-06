from __future__ import annotations

import argparse
import asyncio
import json

from trading_agents.config import settings
from trading_agents.runner import configure_logging, run_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent trading pipeline")
    parser.add_argument("symbols", nargs="*", help="Symbols to analyze (default: from config)")
    args = parser.parse_args()

    configure_logging()
    symbols = args.symbols or settings.symbols
    results = asyncio.run(run_all(symbols))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
