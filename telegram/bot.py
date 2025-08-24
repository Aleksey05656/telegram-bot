# telegram/bot.py
# Логика Telegram-бота: инициализация, обработчики, запуск polling.
import asyncio
import signal
import sys
from typing import Optional, Set

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import BotCommand
from telegram.middlewares import RateLimitMiddleware

from config import settings
from logger import logger

# --- ИСПРАВЛЕНИЕ: Импорт для инициализации кэша ---
from database.cache_postgres import init_cache
# --- Конец ИСПРАВЛЕНИЯ ---


class TelegramBot:
    """Класс для управления Telegram-ботом."""

    def __init__(self):
        """Инициализация Telegram бота."""
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.is_initialized = False
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self._active_tasks: Set[asyncio.Task] = set()
        logger.info("Инициализация TelegramBot")

    async def initialize(self):
        """Асинхронная инициализация бота и диспетчера."""
        if self.is_initialized:
            logger.warning("Бот уже инициализирован")
            return

        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN не указан в переменных окружения!")

        try:
            # Инициализируем бота с настройками
            self.bot = Bot(
                token=settings.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML,
                    link_preview_is_disabled=True  # Отключаем предпросмотр ссылок по умолчанию
                )
            )
            logger.info("✅ Telegram Bot клиент инициализирован")

            # --- ИСПРАВЛЕНИЕ: Инициализация кэша PostgreSQL ---
            logger.info("🚀 Инициализация кэша PostgreSQL...")
            await init_cache()
            logger.info("✅ Кэш PostgreSQL инициализирован")
            # --- Конец ИСПРАВЛЕНИЯ ---

            # Инициализируем диспетчер
            self.dp = Dispatcher()
            self.dp.message.middleware.register(RateLimitMiddleware())
            self.dp.callback_query.middleware.register(RateLimitMiddleware())

            # Регистрируем обработчики команд и коллбэков
            await self._register_handlers()

            # Устанавливаем команды бота
            await self._set_bot_commands()

            self.is_initialized = True
            logger.info("✅ Бот инициализирован успешно")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            raise

    async def _register_handlers(self):
        """Регистрация обработчиков команд и коллбэков."""
        if not self.dp:
            raise RuntimeError("Диспетчер не инициализирован")

        try:
            # Импортируем и регистрируем роутеры
            # ВАЖНО: Порядок регистрации важен! Более специфичные роутеры регистрируем первыми
            from telegram.handlers import start, help, predict, terms

            self.dp.include_router(start.router)
            self.dp.include_router(help.router)
            self.dp.include_router(terms.router)
            self.dp.include_router(predict.router)  # Более общий, регистрируем последним

            logger.info("✅ Роутеры зарегистрированы")
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации роутеров: {e}")
            raise

    async def _set_bot_commands(self):
        """Установка команд бота."""
        if not self.bot:
            return

        try:
            commands = [
                BotCommand(command="start", description="Начало работы с ботом"),
                BotCommand(command="help", description="Помощь и информация"),
                BotCommand(command="predict", description="Сделать прогноз на матч"),
                BotCommand(command="examples", description="Примеры использования"),
                BotCommand(command="stats", description="Статистика бота"),
                BotCommand(command="terms", description="Условия использования"),
                BotCommand(command="disclaimer", description="Отказ от ответственности"),
            ]
            await self.bot.set_my_commands(commands)
            logger.info("✅ Команды бота установлены")
        except TelegramAPIError as e:
            logger.warning(f"⚠️ Ошибка установки команд бота: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Неожиданная ошибка при установке команд: {e}")

    async def on_startup(self):
        """Действия при запуске бота."""
        try:
            if not self.bot:
                raise RuntimeError("Бот не инициализирован")

            # Получаем информацию о боте
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Бот @{bot_info.username} запущен и готов к работе")
            logger.info(f"🤖 Bot ID: {bot_info.id}")

            # Отправка уведомления о запуске (в разработке)
            # if settings.ADMIN_CHAT_ID:
            #     await self.bot.send_message(settings.ADMIN_CHAT_ID, "✅ Бот успешно запущен!")

            if settings.DEBUG_MODE:
                logger.info("🔧 Режим отладки включен")

            self.is_running = True

        except TelegramAPIError as e:
            logger.error(f"❌ Ошибка Telegram API при запуске: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}")

    async def on_shutdown(self):
        """Действия при остановке бота."""
        try:
            logger.info("🛑 Получен сигнал остановки бота...")
            self.is_running = False
            logger.info("✅ Бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения."""
        logger.info(f"Получен сигнал {signum}. Начинаем корректное завершение...")
        self.shutdown_event.set()

    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов."""
        signal.signal(signal.SIGINT, self._signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, self._signal_handler)  # docker stop
        # Для Windows
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)

    async def run(self):
        """Запуск бота с обработкой ошибок."""
        try:
            # Инициализация
            await self.initialize()

            if not self.bot or not self.dp:
                raise RuntimeError("Бот не инициализирован")

            # Настройка обработчиков сигналов
            self._setup_signal_handlers()

            # Регистрация функций запуска/остановки
            self.dp.startup.register(self.on_startup)
            self.dp.shutdown.register(self.on_shutdown)

            # Запуск polling с обработкой ошибок
            logger.info("🚀 Запуск polling...")

            # Создаем задачу для события завершения
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            self._active_tasks.add(shutdown_task)

            try:
                # Запуск polling
                await self.dp.start_polling(
                    self.bot,
                    allowed_updates=["message", "callback_query"],
                    skip_updates=True,  # Пропускаем накопившиеся апдейты
                    handle_as_tasks=True
                )
            finally:
                # Гарантированное завершение
                await self.cleanup()

        except ValueError as e:
            logger.error(f"❌ Ошибка конфигурации: {e}")
            return
        except TelegramAPIError as e:
            logger.error(f"❌ Ошибка Telegram API: {e}")
            return
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения работы (Ctrl+C)")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
            return
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Очистка ресурсов."""
        try:
            logger.info("🧹 Начало очистки ресурсов бота...")

            # Отмена всех активных задач
            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._active_tasks.clear()

            # Закрытие сессии бота
            if self.bot:
                await self.bot.session.close()
                logger.info("✅ Сессия бота закрыта")

            # Очистка диспетчера
            if self.dp:
                await self.dp.fsm.storage.close()
                logger.info("✅ Хранилище FSM закрыто")

            self.is_initialized = False
            self.is_running = False
            logger.info("✅ Ресурсы бота освобождены")

        except Exception as e:
            logger.error(f"❌ Ошибка при очистке ресурсов: {e}")


# Глобальный экземпляр бота
_bot_instance: Optional[TelegramBot] = None


async def get_bot() -> TelegramBot:
    """Фабричная функция для получения экземпляра бота."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance


async def main():
    """Асинхронная точка входа для бота."""
    bot = await get_bot()
    await bot.run()


# Альтернативная функция для использования в других модулях
async def start_bot():
    """Запуск бота (альтернативный способ)."""
    await main()


# Экспорт класса и функций
__all__ = ["TelegramBot", "main", "start_bot", "get_bot"]
