"""
@file: scripts/tg_bot.py
@description: Telegram bot entrypoint with graceful shutdown handling
@dependencies: telegram.bot, logger
@created: 2025-10-27
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

from logger import logger
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
