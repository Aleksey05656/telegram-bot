# main.py
import argparse
import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from config import settings

# --- Импорты, выполненные в начале файла ---
from database.cache_postgres import init_cache
from logger import logger
from ml.models.poisson_regression_model import poisson_regression_model
from telegram.bot import main as bot_main  # Импорт перемещён сюда

# Глобальная переменная для управления завершением
shutdown_event = asyncio.Event()


@asynccontextmanager
async def app_lifespan(dry_run: bool = False):
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

    if dry_run:
        logger.info("Dry-run: пропуск запуска polling из main")
        try:
            yield
        finally:
            logger.info("Dry-run: завершение приложения")
        return

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
        except TimeoutError:
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
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)


async def main(dry_run: bool = False):
    """Главная асинхронная точка входа приложения."""
    async with app_lifespan(dry_run=dry_run):
        if dry_run:
            await bot_main(dry_run=True)
            return
        # Ожидаем сигнал завершения
        await shutdown_event.wait()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram bot runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Инициализировать зависимости и завершиться без запуска polling",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        asyncio.run(main(dry_run=args.dry_run))
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt. Завершение работы.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        sys.exit(1)
