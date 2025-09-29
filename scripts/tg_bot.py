"""
@file: scripts/tg_bot.py
@description: Telegram bot entrypoint with graceful shutdown handling
@dependencies: telegram.bot, logger
@created: 2025-10-27
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import signal
import sys
from contextlib import suppress
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_logger() -> logging.Logger:
    candidates = (
        ("logger", "logger"),
        ("app.logger", "logger"),
        ("common.logger", "logger"),
        ("app.utils.logger", "logger"),
    )

    for module_name, attribute_name in candidates:
        try:
            module = importlib.import_module(module_name)
            candidate = getattr(module, attribute_name)
        except ModuleNotFoundError:
            continue
        except AttributeError:
            continue
        else:
            if isinstance(candidate, logging.Logger):
                candidate.info("custom logger resolved from %s.%s", module_name, attribute_name)
                return candidate
            if callable(candidate):
                resolved = candidate()
                if isinstance(resolved, logging.Logger):
                    resolved.info("custom logger resolved from %s.%s", module_name, attribute_name)
                    return resolved

    logging.basicConfig()
    fallback_logger = logging.getLogger("tg_bot")
    fallback_logger.warning("fallback logger activated")
    return fallback_logger


logger = _resolve_logger()

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
