"""
@file: scripts/tg_bot.py
@description: Resilient Telegram bot polling entrypoint with graceful restarts.
@dependencies: aiogram, tgbotapp.handlers, tgbotapp.middlewares
@created: 2025-11-16
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import signal
import sys
from contextlib import suppress
from pathlib import Path
from types import FrameType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

try:
    from logger import logger  # type: ignore
except Exception:  # pragma: no cover - fallback logger
    logger = logging.getLogger("tg_bot")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    RestartingTelegram,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import BotCommand

from app.runtime_state import STATE
from app.utils.retry import retry_async
from config import settings
from database.cache_postgres import init_cache
from tgbotapp.handlers import register_handlers
from tgbotapp.middlewares import (
    IdempotencyMiddleware,
    ProcessingTimeMiddleware,
    RateLimitMiddleware,
)

COMMANDS: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="Начало работы"),
    BotCommand(command="help", description="Справка и примеры"),
    BotCommand(command="today", description="Матчи на сегодня"),
    BotCommand(command="match", description="Карточка матча"),
    BotCommand(command="explain", description="Объяснить прогноз"),
    BotCommand(command="league", description="Матчи лиги"),
    BotCommand(command="subscribe", description="Ежедневный дайджест"),
    BotCommand(command="settings", description="Личные настройки"),
    BotCommand(command="export", description="Экспорт отчёта"),
    BotCommand(command="about", description="Версии и статус"),
)

POLLING_ALLOWED_UPDATES: tuple[str, ...] = ("message", "callback_query")
POLLING_TIMEOUT = 30
BACKOFF_BASE = 1.0
BACKOFF_JITTER = 0.3
BACKOFF_MAX = 60.0


def _compute_backoff(attempt: int) -> float:
    base_delay = min(BACKOFF_MAX, BACKOFF_BASE * (2**max(attempt, 0)))
    jitter = base_delay * BACKOFF_JITTER
    return max(0.1, random.uniform(base_delay - jitter, base_delay + jitter))


def _setup_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _handle_signal(signum: int, _frame: FrameType | None) -> None:  # pragma: no cover - signal path
        try:
            signal_name = signal.Signals(signum).name
        except ValueError:
            signal_name = str(signum)
        logger.info("Shutdown signal received: %s", signal_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover - platform dependent
            signal.signal(sig, _handle_signal)


async def _prepare_dependencies() -> None:
    await retry_async(init_cache)


async def _create_application() -> tuple[Bot, Dispatcher]:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured")

    await _prepare_dependencies()

    session = AiohttpSession()
    try:
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
            ),
        )
    except Exception:
        await session.close()
        raise

    dispatcher = Dispatcher()

    message_rate = RateLimitMiddleware()
    callback_rate = RateLimitMiddleware()
    dispatcher.message.middleware.register(message_rate)
    dispatcher.callback_query.middleware.register(callback_rate)
    dispatcher.message.middleware.register(IdempotencyMiddleware())
    timing = ProcessingTimeMiddleware()
    dispatcher.message.middleware.register(timing)
    dispatcher.callback_query.middleware.register(timing)

    register_handlers(dispatcher)

    await retry_async(bot.set_my_commands, list(COMMANDS))

    dispatcher.startup.register(_on_startup)
    dispatcher.shutdown.register(_on_shutdown)

    return bot, dispatcher


async def _on_startup(bot: Bot) -> None:
    bot_info = await retry_async(bot.get_me)
    STATE.polling_ready = True
    logger.info("Bot @%s (id=%s) is ready", bot_info.username, bot_info.id)
    if settings.DEBUG_MODE:
        logger.info("Debug mode is enabled")


async def _on_shutdown(_: Dispatcher) -> None:
    STATE.polling_ready = False
    logger.info("Bot shutdown complete")


async def _run_polling(
    bot: Bot,
    dispatcher: Dispatcher,
    stop_event: asyncio.Event,
) -> None:
    polling_task = asyncio.create_task(
        dispatcher.start_polling(
            bot,
            allowed_updates=POLLING_ALLOWED_UPDATES,
            skip_updates=True,
            handle_signals=False,
            polling_timeout=POLLING_TIMEOUT,
        )
    )
    stopper = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait(
        {polling_task, stopper},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stopper in done:
        logger.info("Shutdown requested, stopping polling")
        await dispatcher.stop_polling()
        if polling_task in pending:
            polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await polling_task
    else:
        await polling_task

    stopper.cancel()
    with suppress(asyncio.CancelledError):
        await stopper


async def main_async() -> None:
    logger.info("Starting Telegram polling worker (token configured: %s)", bool(settings.TELEGRAM_BOT_TOKEN))
    stop_event = asyncio.Event()
    _setup_signal_handlers(stop_event)

    attempt = 0
    while not stop_event.is_set():
        bot: Bot | None = None
        dispatcher: Dispatcher | None = None
        try:
            bot, dispatcher = await _create_application()
            await _run_polling(bot, dispatcher, stop_event)
            if not stop_event.is_set():
                logger.info("Polling loop completed without shutdown request")
            break
        except TelegramRetryAfter as exc:
            wait_time = max(float(exc.retry_after), 0.0)
            logger.warning("Rate limited by Telegram. Sleeping for %.2f seconds", wait_time)
            await asyncio.sleep(wait_time)
            attempt = 0
        except (RestartingTelegram, TelegramNetworkError) as exc:
            wait_time = _compute_backoff(attempt)
            attempt += 1
            logger.warning("Temporary Telegram error (%s). Retrying in %.2f seconds", exc.__class__.__name__, wait_time)
            await asyncio.sleep(wait_time)
        except Exception as exc:  # pragma: no cover - defensive path
            wait_time = _compute_backoff(attempt)
            attempt += 1
            logger.exception("Unexpected error in polling loop: %s. Retrying in %.2f seconds", exc, wait_time)
            await asyncio.sleep(wait_time)
        finally:
            if dispatcher is not None:
                storage = getattr(getattr(dispatcher, "fsm", None), "storage", None)
                if storage is not None:
                    with suppress(Exception):
                        await storage.close()
            if bot is not None:
                with suppress(Exception):
                    await bot.session.close()
            STATE.polling_ready = False
        if stop_event.is_set():
            break
        await asyncio.sleep(0)

    logger.info("Telegram polling worker stopped")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
