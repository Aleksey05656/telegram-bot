# main.py
import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from logger import logger
from config import settings

# --- Импорты, выполненные в начале файла ---
from database.cache_postgres import init_cache
from ml.models.poisson_regression_model import poisson_regression_model
from telegram.bot import main as bot_main  # Импорт перемещён сюда

# Глобальная переменная для управления завершением
shutdown_event = asyncio.Event()


@asynccontextmanager
async def app_lifespan():
    """Контекстный менеджер для инициализации и завершения приложения."""
    logger.info("Приложение запускается...")
    setup_signal_handlers()
    logger.info(f"Запуск бота в режиме DEBUG={settings.DEBUG_MODE}")
    logger.info(f"Уровень логирования: {settings.LOG_LEVEL}")

    # Инициализация кэша и модели
    logger.info("Инициализация PostgreSQL кэша")
    await init_cache()

    logger.info("Загрузка рейтингов команд из data/team_ratings.json")
    # load_ratings — синхронный метод, await не нужен
    poisson_regression_model.load_ratings()

    # Запуск бота
    bot_task = asyncio.create_task(bot_main())

    try:
        yield
    finally:
        logger.info("Приложение завершает работу...")
        shutdown_event.set()

        # Ожидание завершения бота с таймаутом
        try:
            await asyncio.wait_for(bot_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Завершение бота превысило таймаут")

        logger.info("✅ Приложение остановлено")


def setup_signal_handlers():
    """Настройка обработчиков системных сигналов для graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}. Инициируем graceful shutdown...")
        shutdown_event.set()

        # Сброс обработчика, чтобы не срабатывал повторно
        signal.signal(signum, signal.SIG_DFL)

    # Регистрация обработчиков
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Для Windows (Ctrl+C)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)


async def main():
    """Главная асинхронная точка входа приложения."""
    async with app_lifespan():
        # Ожидаем сигнал завершения
        await shutdown_event.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt. Завершение работы.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        sys.exit(1)
