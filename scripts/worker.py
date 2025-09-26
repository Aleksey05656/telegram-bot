"""
@file: scripts/worker.py
@description: Worker entrypoint orchestrating periodic data refresh pipeline
@dependencies: scripts.update_upcoming, logger
@created: 2025-10-27
"""

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress

from logger import logger
from scripts.update_upcoming import refresh_upcoming


async def _run_refresh(days: int) -> None:
    logger.info("worker.refresh.start days=%s", days)
    await refresh_upcoming(days)
    logger.info("worker.refresh.done days=%s", days)


async def _worker_loop(shutdown: asyncio.Event) -> None:
    days = int(os.getenv("WORKER_REFRESH_DAYS", "3"))
    interval = float(os.getenv("WORKER_INTERVAL_SECONDS", "900"))
    while not shutdown.is_set():
        try:
            await _run_refresh(days)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("worker.refresh.error: %s", exc)
        if interval <= 0:
            break
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def _install_signal_handlers(shutdown: asyncio.Event) -> None:
    def _handler(signum: int, frame) -> None:  # pragma: no cover - signal handler
        logger.info("worker.signal received=%s", signal.Signals(signum).name)
        shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(ValueError):
            signal.signal(sig, _handler)


async def main_async() -> None:
    shutdown = asyncio.Event()
    _install_signal_handlers(shutdown)
    await _worker_loop(shutdown)
    logger.info("worker.shutdown.complete")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
