# @file: telegram/bot.py
# Логика Telegram-бота: инициализация, обработчики, запуск polling.
import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand

from app.runtime_state import STATE
from app.utils import retry_async
from config import settings
from database.cache_postgres import init_cache
from logger import logger
from .middlewares import (
    IdempotencyMiddleware,
    ProcessingTimeMiddleware,
    RateLimitMiddleware,
)


class TelegramBot:
    """Класс для управления Telegram-ботом."""

    def __init__(self) -> None:
        self.bot: Bot | None = None
        self.dp: Dispatcher | None = None
        self.is_initialized = False
        self.is_running = False
        self._internal_shutdown = asyncio.Event()
        self._active_shutdown: asyncio.Event | None = None
        self._active_tasks: set[asyncio.Task] = set()
        logger.info("Инициализация TelegramBot")

    async def initialize(self) -> None:
        """Асинхронная инициализация бота и диспетчера."""
        if self.is_initialized:
            logger.warning("Бот уже инициализирован")
            return

        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN не указан в переменных окружения!")

        try:
            self.bot = Bot(
                token=settings.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML,
                    link_preview_is_disabled=True,
                ),
            )
            logger.info("✅ Telegram Bot клиент инициализирован")

            logger.info("🚀 Инициализация кэша PostgreSQL...")
            await retry_async(init_cache)
            logger.info("✅ Кэш PostgreSQL инициализирован")

            self.dp = Dispatcher()
            message_rate = RateLimitMiddleware()
            callback_rate = RateLimitMiddleware()
            self.dp.message.middleware.register(message_rate)
            self.dp.callback_query.middleware.register(callback_rate)
            self.dp.message.middleware.register(IdempotencyMiddleware())
            timing = ProcessingTimeMiddleware()
            self.dp.message.middleware.register(timing)
            self.dp.callback_query.middleware.register(timing)

            await self._register_handlers()
            await retry_async(self._set_bot_commands)

            self.is_initialized = True
            logger.info("✅ Бот инициализирован успешно")

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Ошибка инициализации бота: %s", exc)
            raise

    async def _register_handlers(self) -> None:
        if not self.dp:
            raise RuntimeError("Диспетчер не инициализирован")
        try:
            from .handlers import register_handlers

            register_handlers(self.dp)
            logger.info("✅ Роутеры зарегистрированы")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Ошибка регистрации роутеров: %s", exc)
            raise

    async def _set_bot_commands(self) -> None:
        if not self.bot:
            return
        try:
            commands = [
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
            ]
            await self.bot.set_my_commands(commands)
            logger.info("✅ Команды бота установлены")
        except TelegramAPIError as exc:
            logger.warning("⚠️ Ошибка установки команд бота: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("⚠️ Неожиданная ошибка при установке команд: %s", exc)

    async def on_startup(self) -> None:
        try:
            if not self.bot:
                raise RuntimeError("Бот не инициализирован")
            bot_info = await retry_async(self.bot.get_me)
            logger.info("✅ Бот @%s запущен и готов к работе", bot_info.username)
            logger.info("🤖 Bot ID: %s", bot_info.id)
            if settings.DEBUG_MODE:
                logger.info("🔧 Режим отладки включен")
            self.is_running = True
            STATE.polling_ready = True
        except TelegramAPIError as exc:
            logger.error("❌ Ошибка Telegram API при запуске: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Ошибка при запуске бота: %s", exc)

    async def on_shutdown(self) -> None:
        try:
            logger.info("🛑 Получен сигнал остановки бота...")
            self.is_running = False
            STATE.polling_ready = False
            logger.info("✅ Бот остановлен")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Ошибка при остановке бота: %s", exc)

    async def run(
        self,
        dry_run: bool = False,
        shutdown_event: asyncio.Event | None = None,
    ) -> None:
        try:
            try:
                delay = max(0.0, float(settings.STARTUP_DELAY_SEC))
            except (TypeError, ValueError):
                delay = 0.0
            if delay:
                logger.info("⏳ Ожидание перед инициализацией бота %.2f c", delay)
                await asyncio.sleep(delay)

            await self.initialize()

            if not self.bot or not self.dp:
                raise RuntimeError("Бот не инициализирован")

            if dry_run:
                logger.info("🚦 Dry-run: пропуск запуска polling")
                await self.cleanup()
                return

            self._active_shutdown = shutdown_event or self._internal_shutdown

            self.dp.startup.register(self.on_startup)
            self.dp.shutdown.register(self.on_shutdown)

            logger.info("🚀 Запуск polling...")
            polling_task = asyncio.create_task(
                self.dp.start_polling(
                    self.bot,
                    allowed_updates=["message", "callback_query"],
                    skip_updates=True,
                    handle_as_tasks=True,
                )
            )
            shutdown_task = asyncio.create_task(self._active_shutdown.wait())
            self._active_tasks.update({polling_task, shutdown_task})

            done, pending = await asyncio.wait(
                {polling_task, shutdown_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if shutdown_task in done:
                logger.info("🛑 Сигнал остановки получен, завершаем polling...")
                try:
                    await self.dp.stop_polling()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Ошибка при остановке polling: %s", exc)
                if polling_task in pending or not polling_task.done():
                    polling_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await polling_task

        except ValueError as exc:
            logger.error("❌ Ошибка конфигурации: %s", exc)
        except TelegramAPIError as exc:
            logger.error("❌ Ошибка Telegram API: %s", exc)
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения работы (Ctrl+C)")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Критическая ошибка при запуске бота: %s", exc, exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        try:
            logger.info("🧹 Начало очистки ресурсов бота...")

            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            self._active_tasks.clear()

            if self.bot:
                await self.bot.session.close()
                logger.info("✅ Сессия бота закрыта")

            if self.dp:
                await self.dp.fsm.storage.close()
                logger.info("✅ Хранилище FSM закрыто")

            self.is_initialized = False
            self.is_running = False
            STATE.polling_ready = False
            if self._active_shutdown is None or self._active_shutdown is self._internal_shutdown:
                self._internal_shutdown = asyncio.Event()
            self._active_shutdown = None
            logger.info("✅ Ресурсы бота освобождены")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Ошибка при очистке ресурсов: %s", exc)

    async def stop(self) -> None:
        logger.info("🛑 Запрошена остановка TelegramBot")
        (self._active_shutdown or self._internal_shutdown).set()
        if self.dp:
            try:
                await self.dp.stop_polling()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Ошибка при остановке polling: %s", exc)


_bot_instance: TelegramBot | None = None


async def get_bot() -> TelegramBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance


async def main(
    dry_run: bool = False,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    bot = await get_bot()
    await bot.run(dry_run=dry_run, shutdown_event=shutdown_event)


async def start_bot(dry_run: bool = False) -> None:
    await main(dry_run=dry_run)


__all__ = ["TelegramBot", "main", "start_bot", "get_bot"]
