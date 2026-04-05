"""Entry point for the Polymarket Watcher service.

Usage
-----
Run as a module::

    python -m polymarket_watcher [path/to/config.yaml]
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import Config
from .service import WatcherService


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def main() -> None:
    """Parse arguments, load config, and run the service."""
    config_path: Path | None = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    cfg = Config.from_yaml(config_path)

    _setup_logging(cfg.service.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting Polymarket Watcher…")

    service = WatcherService(cfg)
    loop = asyncio.new_event_loop()

    def _shutdown() -> None:
        logger.info("Shutdown signal received; cancelling tasks…")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    try:
        loop.run_until_complete(service.run())
    except asyncio.CancelledError:
        logger.info("Service stopped cleanly.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
