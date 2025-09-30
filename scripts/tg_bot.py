"""
@file: scripts/tg_bot.py
@description: Telegram bot entrypoint with graceful shutdown handling
@dependencies: telegram.bot, logger
@created: 2025-10-27
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
_fallback_logger = logging.getLogger("tg_bot")

try:
    from logger import logger as _logger

    logger = _logger
except Exception:  # pragma: no cover - defensive
    logger = _fallback_logger
    logger.warning("tg_bot: fallback logger activated")

logger.info(
    "tg_bot bootstrap: ROOT=%s PYTHONPATH=%s",
    ROOT,
    os.getenv("PYTHONPATH", ""),
)
logger.info(
    "telegram.middlewares present? %s",
    importlib.util.find_spec("telegram.middlewares") is not None,
)

try:  # pragma: no cover - optional build metadata logging
    from app.build_meta import get_build_meta

    _build_meta = get_build_meta()
    logger.info(
        "build: repo=%s branch=%s commit=%s built_at=%s",
        _build_meta.get("repo"),
        _build_meta.get("branch"),
        _build_meta.get("commit"),
        _build_meta.get("built_at"),
    )
except Exception:
    pass

from telegram.bot import TelegramBot


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    def _handler(signum: int, frame) -> None:  # pragma: no cover - signal handler
        logger.info("tgbot.signal received=%s", signal.Signals(signum).name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(ValueError):
            signal.signal(sig, _handler)


async def main_async() -> None:
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    bot = TelegramBot()
    await bot.run(shutdown_event=stop_event)
    logger.info("tgbot.shutdown.complete")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
