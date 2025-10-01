# @file: main.py
import argparse
import asyncio
import contextlib
import os
import signal
import sys
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from app.db_maintenance import backup_sqlite, vacuum_analyze
from app.health import HealthServer
from app.metrics import (
    periodic_db_size_updater,
    record_retrain_failure,
    record_retrain_success,
    start_metrics_server,
)
from app.runtime_lock import RuntimeLock, RuntimeLockError
from app.runtime_state import STATE
from app.utils import retry_async
from config import settings
from database.cache_postgres import init_cache, shutdown_cache
from logger import logger
from ml.models.poisson_regression_model import poisson_regression_model
from tgbotapp.bot import get_bot
from workers.retrain_scheduler import schedule_retrain
from workers.runtime_scheduler import clear_jobs, register as register_runtime_job

shutdown_event = asyncio.Event()
_runtime_lock: RuntimeLock | None = None
_health_server: HealthServer | None = None
_metrics_task: asyncio.Task | None = None
_backup_task: asyncio.Task | None = None
_vacuum_task: asyncio.Task | None = None


def _ensure_writable(path: Path, label: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    test_file = path / ".amvera_write_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        logger.info("Проверка записи для %s: %s", label, path)
    finally:
        try:
            test_file.unlink()
        except FileNotFoundError:
            pass


def log_runtime_paths() -> None:
    logger.info("DATA_ROOT=%s", settings.DATA_ROOT)
    logger.info("DB_PATH=%s", settings.DB_PATH)
    logger.info("REPORTS_DIR=%s", settings.REPORTS_DIR)
    logger.info("MODEL_REGISTRY_PATH=%s", settings.MODEL_REGISTRY_PATH)
    logger.info("LOG_DIR=%s", settings.LOG_DIR)
    _ensure_writable(Path(settings.LOG_DIR), "LOG_DIR")
    _ensure_writable(Path(settings.REPORTS_DIR), "REPORTS_DIR")
    _ensure_writable(Path(settings.MODEL_REGISTRY_PATH), "MODEL_REGISTRY_PATH")


def setup_signal_handlers() -> None:
    def _handler(signum, _frame) -> None:
        logger.info("Получен сигнал %s. Инициируем graceful shutdown...", signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handler)


def _register_retrain_job() -> tuple[bool, str | None]:
    if not settings.ENABLE_SCHEDULER:
        logger.info("Планировщик retrain отключен (ENABLE_SCHEDULER=0)")
        return False, None
    if settings.FAILSAFE_MODE:
        logger.warning("Failsafe mode активен — планировщик retrain пропущен")
        return False, None

    cron_raw = os.getenv("RETRAIN_CRON", "").strip()
    if not cron_raw or cron_raw.lower() in {"off", "disabled", "none", "false"}:
        return False, None
    try:
        effective = schedule_retrain(register_runtime_job, cron_expr=cron_raw or None)
        logger.info("Регистрация retrain job с cron=%s", effective)
        record_retrain_success()
        return True, effective
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Не удалось зарегистрировать retrain job: %s", exc)
        record_retrain_failure()
        return False, None


async def _periodic_executor(
    label: str, interval: float, runner: Callable[[], None]
) -> None:
    loop = asyncio.get_running_loop()
    while not shutdown_event.is_set():
        try:
            await loop.run_in_executor(None, runner)
            logger.info("%s выполнено успешно", label)
        except FileNotFoundError:
            logger.warning("%s: файл базы данных не найден", label)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("%s завершилось с ошибкой: %s", label, exc)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def app_lifespan(dry_run: bool = False):
    global _runtime_lock, _health_server, _metrics_task, _backup_task, _vacuum_task
    _runtime_lock = RuntimeLock(Path(settings.RUNTIME_LOCK_PATH))
    _metrics_task = None
    _backup_task = None
    _vacuum_task = None
    STATE.started_at = time.time()
    STATE.db_ready = False
    STATE.polling_ready = not settings.ENABLE_POLLING
    STATE.scheduler_ready = (
        not settings.ENABLE_SCHEDULER or settings.FAILSAFE_MODE
    )
    canary_mode = bool(getattr(settings, "CANARY", False))
    if canary_mode:
        STATE.scheduler_ready = True
    await _runtime_lock.acquire()
    try:
        setup_signal_handlers()
        logger.info("Приложение запускается (dry_run=%s)", dry_run)
        logger.info("DEBUG=%s LOG_LEVEL=%s", settings.DEBUG_MODE, settings.LOG_LEVEL)
        shutdown_event.clear()

        await retry_async(init_cache)
        STATE.db_ready = True
        poisson_regression_model.load_ratings()

        retrain_enabled = False
        effective_cron = None
        if not canary_mode:
            retrain_enabled, effective_cron = _register_retrain_job()
            if retrain_enabled:
                logger.info("Retrain scheduler активирован: cron=%s", effective_cron)
                STATE.scheduler_ready = True
        else:
            logger.info("CANARY=1 — пропуск регистрации retrain scheduler")

        if settings.ENABLE_HEALTH:
            _health_server = HealthServer(settings.HEALTH_HOST, settings.HEALTH_PORT)
            await _health_server.start()
        else:
            _health_server = None

        if settings.ENABLE_METRICS and not canary_mode:
            try:
                start_metrics_server(int(settings.METRICS_PORT))
            except OSError as exc:  # pragma: no cover - port already in use
                logger.warning("Не удалось запустить сервер метрик: %s", exc)
            else:
                _metrics_task = asyncio.create_task(
                    periodic_db_size_updater(
                        settings.DB_PATH,
                        interval=60.0,
                        stop_event=shutdown_event,
                    )
                )
        elif settings.ENABLE_METRICS and canary_mode:
            logger.info("CANARY=1 — сервер метрик не запускается")

        if not settings.FAILSAFE_MODE and not canary_mode:
            _backup_task = asyncio.create_task(
                _periodic_executor(
                    "SQLite backup",
                    24 * 60 * 60,
                    lambda: backup_sqlite(
                        settings.DB_PATH,
                        settings.BACKUP_DIR,
                        keep=settings.BACKUP_KEEP,
                    ),
                )
            )
            _vacuum_task = asyncio.create_task(
                _periodic_executor(
                    "SQLite vacuum/analyze",
                    7 * 24 * 60 * 60,
                    lambda: vacuum_analyze(settings.DB_PATH),
                )
            )
            if settings.ENABLE_SCHEDULER:
                STATE.scheduler_ready = True
        elif not settings.FAILSAFE_MODE and canary_mode:
            logger.info("CANARY=1 — фоновые задачи резервного копирования отключены")

        try:
            yield
        finally:
            logger.info("Завершение приложения...")
            for task in (_metrics_task, _backup_task, _vacuum_task):
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            _metrics_task = None
            _backup_task = None
            _vacuum_task = None
            if _health_server:
                await _health_server.stop()
                _health_server = None
            await shutdown_cache()
            clear_jobs()
            STATE.db_ready = False
            STATE.polling_ready = False
            STATE.scheduler_ready = False
            logger.info("✅ Ресурсы приложения освобождены")
    finally:
        if _runtime_lock:
            await _runtime_lock.release()
            _runtime_lock = None


async def main(dry_run: bool = False) -> None:
    try:
        async with app_lifespan(dry_run=dry_run):
            log_runtime_paths()
            if getattr(settings, "CANARY", False):
                logger.warning("CANARY=1 — запуск Telegram бота пропущен")
                STATE.polling_ready = True
                await shutdown_event.wait()
                return
            bot = await get_bot()
            if dry_run:
                await bot.run(dry_run=True, shutdown_event=shutdown_event)
                return

            if not settings.ENABLE_POLLING:
                logger.info("Polling отключен (ENABLE_POLLING=0), ожидание сигнала")
                STATE.polling_ready = True
                await shutdown_event.wait()
                return

            bot_task = asyncio.create_task(
                bot.run(dry_run=False, shutdown_event=shutdown_event)
            )
            shutdown_wait = asyncio.create_task(shutdown_event.wait())

            done, pending = await asyncio.wait(
                {bot_task, shutdown_wait}, return_when=asyncio.FIRST_COMPLETED
            )

            if shutdown_wait in done:
                logger.info("Получен сигнал завершения, останавливаем бота")
                await bot.stop()
                try:
                    await asyncio.wait_for(
                        bot_task, timeout=settings.SHUTDOWN_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "⚠️ Завершение бота превысило таймаут %.1f c",
                        settings.SHUTDOWN_TIMEOUT,
                    )
            else:
                logger.warning("Polling завершился раньше сигнала shutdown")
                shutdown_wait.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await shutdown_wait
    except RuntimeLockError as exc:
        logger.error("Приложение уже запущено: %s", exc)


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
    except Exception as exc:  # pragma: no cover - defensive
        logger.critical("Критическая ошибка при запуске приложения: %s", exc, exc_info=True)
        sys.exit(1)
