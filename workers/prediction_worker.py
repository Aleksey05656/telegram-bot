# workers/prediction_worker.py
import asyncio
import time
import signal
from typing import Optional, Tuple, Any
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from logger import logger
from config import settings
from database.cache_postgres import cache, init_cache
from services.data_processor import DataProcessor
from services.recommendation_engine import recommendation_engine
from telegram.utils.formatter import format_prediction_result
from ml.models.poisson_regression_model import poisson_regression_model

# Константы для сообщений
ERROR_MESSAGE = "❌ Произошла внутренняя ошибка при генерации прогноза. Попробуйте позже."
WARNING_MODEL_OUTDATED = (
    "⚠️ <b>Внимание!</b>\n"
    "Данные для прогнозирования устарели. \n"
    "Результаты могут быть менее точными. \n"
    "Администратор уведомлен о необходимости обновления."
)

class PredictionWorker:
    """Воркер для асинхронной обработки задач прогнозирования."""
    
    def __init__(self):
        """Инициализация Prediction Worker."""
        self.bot: Optional[Bot] = None
        self.is_running = True
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.start_time: Optional[float] = None
        logger.info("Инициализация PredictionWorker")

    async def initialize(self):
        """Инициализация бота и других компонентов."""
        try:
            if not settings.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
            
            # Инициализация бота
            self.bot = Bot(
                token=settings.TELEGRAM_BOT_TOKEN, 
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            self.start_time = time.time()
            
            # Инициализация кэша
            await init_cache()
            
            # Загружаем рейтинги модели
            await poisson_regression_model.load_ratings()
            logger.info("✅ PredictionWorker инициализирован успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации PredictionWorker: {e}")
            raise

    async def process_prediction(self, chat_id: int, home_team: str, away_team: str, job_id: str) -> bool:
        """Асинхронная обработка прогнозирования.
        
        Args:
            chat_id (int): ID чата для отправки результата
            home_team (str): Название домашней команды
            away_team (str): Название гостевой команды
            job_id (str): ID задачи
            
        Returns:
            bool: Успешность обработки
        """
        start_time = time.time()
        logger.info(f"[{job_id}] Начало обработки прогноза для {home_team} vs {away_team}")
        lock = None
        if cache and cache.redis_client:
            lock_key = f"prediction_lock:{home_team}:{away_team}"
            lock = cache.redis_client.lock(lock_key, timeout=60)
            if not await lock.acquire(blocking=False):
                logger.warning(
                    f"[{job_id}] Прогноз уже генерируется для {home_team} vs {away_team}"
                )
                await self._send_message(
                    chat_id,
                    "⚠️ Прогноз уже генерируется для этого матча. Попробуйте позже.",
                )
                return False
        
        try:
            # Проверка актуальности модели
            if poisson_regression_model.is_model_outdated():
                logger.warning(f"[{job_id}] Модель устарела при запросе прогноза {home_team} vs {away_team}")
                await self._send_message(chat_id, WARNING_MODEL_OUTDATED)

            # Отправка уведомления о начале обработки
            await self._send_message(
                chat_id,
                f"⏳ Начинаем генерацию прогноза для <b>{home_team} - {away_team}</b>..."
            )

            # Получение расширенных данных
            processor = DataProcessor()
            success, data, error = await processor.get_augmented_data(home_team, away_team)
            
            if not success:
                error_msg = f"❌ Не удалось получить данные для прогноза: {error}"
                logger.error(f"[{job_id}] {error_msg}")
                await self._send_message(chat_id, error_msg)
                self.failed_jobs += 1
                return False

            match_data, team_stats, h2h_data = data

            # Генерация комплексного прогноза
            prediction = await recommendation_engine.generate_comprehensive_prediction(match_data, team_stats)

            # Форматирование результата
            formatted_result = format_prediction_result(prediction, match_data, team_stats, h2h_data)

            # Отправка результата пользователю
            await self._send_message(chat_id, formatted_result)

            processing_time = time.time() - start_time
            logger.info(f"[{job_id}] ✅ Прогноз успешно сгенерирован за {processing_time:.2f} секунд")
            self.processed_jobs += 1
            return True

        except Exception as e:
            logger.error(f"[{job_id}] Критическая ошибка в worker: {e}", exc_info=True)
            await self._send_error_message(chat_id)
            self.failed_jobs += 1
            return False
        finally:
            if lock and lock.locked():
                try:
                    await lock.release()
                except Exception as e:  # pragma: no cover - non-critical
                    logger.error(f"[{job_id}] Ошибка освобождения Redis-lock: {e}")

    async def _send_message(self, chat_id: int, text: str) -> None:
        """Вспомогательный метод для отправки сообщений."""
        if self.bot is not None:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")

    async def _send_error_message(self, chat_id: int) -> None:
        """Отправка сообщения об ошибке пользователю."""
        await self._send_message(chat_id, ERROR_MESSAGE)

    async def run_single_job(self, chat_id: int, home_team: str, away_team: str, job_id: str):
        """Запуск одной задачи прогнозирования."""
        try:
            await self.initialize()
            await self.process_prediction(chat_id, home_team, away_team, job_id)
        except Exception as e:
            logger.error(f"[{job_id}] Ошибка при выполнении одиночной задачи: {e}", exc_info=True)
        finally:
            # Здесь можно добавить логику очистки ресурсов
            pass

    async def run_continuous(self):
        """Непрерывный режим работы воркера."""
        logger.info("Запуск PredictionWorker в непрерывном режиме")
        try:
            await self.initialize()
            
            # Регистрация обработчиков сигналов
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, 
                    lambda: asyncio.create_task(self.shutdown())
                )

            # В непрерывном режиме worker обычно прослушивает очередь задач
            # Здесь должна быть логика получения задач из очереди RQ
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Фатальная ошибка в непрерывном режиме: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы воркера."""
        logger.info("Завершение работы PredictionWorker...")
        self.is_running = False
        
        # Закрываем соединение с ботом если оно открыто
        if self.bot is not None and not self.bot.session.closed:
            await self.bot.session.close()

        # Логируем статистику
        uptime = time.time() - self.start_time if self.start_time else 0
        logger.info(
            f"PredictionWorker остановлен. "
            f"Обработано: {self.processed_jobs}, "
            f"Ошибок: {self.failed_jobs}, "
            f"Время работы: {uptime:.2f} сек"
        )

# Создание экземпляра воркера
worker = PredictionWorker()

async def main():
    """Основная точка входа для воркера."""
    import sys
    
    if len(sys.argv) < 2:
        print("Использование:")
        print(" Для одной задачи: python prediction_worker.py single <chat_id> <home_team> <away_team> <job_id>")
        print(" Непрерывный режим: python prediction_worker.py continuous")
        sys.exit(1)

    mode = sys.argv[1]
    
    try:
        if mode == "single" and len(sys.argv) == 6:
            # Обработка одной задачи
            chat_id = int(sys.argv[2])
            home_team = sys.argv[3]
            away_team = sys.argv[4]
            job_id = sys.argv[5]
            await worker.run_single_job(chat_id, home_team, away_team, job_id)
        elif mode == "continuous" and len(sys.argv) == 2:
            # Непрерывный режим работы
            await worker.run_continuous()
        else:
            print("Некорректные аргументы")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения (Ctrl+C)")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        sys.exit(1)

# --- ФУНКЦИЯ ДЛЯ ВЫЗОВА ИЗ RQ ---
# Эта функция должна быть синхронной, так как вызывается RQ напрямую.
# Внутри она запускает асинхронную логику.

def process_prediction(chat_id: int, home_team: str, away_team: str, job_id: str) -> bool:
    """
    Функция для вызова из очереди задач RQ.
    Эта функция должна быть синхронной, так как вызывается RQ.
    Внутри она запускает асинхронную логику.
    """
    try:
        logger.info(f"[{job_id}] Начало задачи прогнозирования через RQ для {home_team} vs {away_team}")
        
        # Получаем или создаем event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Запускаем асинхронную функцию обработки
        result = loop.run_until_complete(_async_process_prediction(chat_id, home_team, away_team, job_id))
        logger.info(f"[{job_id}] ✅ Задача прогнозирования через RQ завершена успешно")
        return result
        
    except Exception as e:
        logger.error(f"[{job_id}] ❌ Критическая ошибка в функции process_prediction (RQ): {e}", exc_info=True)
        
        # Отправка сообщения об ошибке пользователю
        try:
            try:
                error_loop = asyncio.get_event_loop()
            except RuntimeError:
                error_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(error_loop)
            error_loop.run_until_complete(_send_error_message_to_user(chat_id))
        except Exception as send_error:
            logger.error(f"[{job_id}] Ошибка при отправке сообщения об ошибке пользователю: {send_error}")
        
        return False  # Возвращаем False в случае ошибки

async def _async_process_prediction(chat_id: int, home_team: str, away_team: str, job_id: str) -> bool:
    """Внутренняя асинхронная функция для выполнения логики прогнозирования."""
    # Используем глобальный экземпляр воркера
    await worker.initialize()
    return await worker.process_prediction(chat_id, home_team, away_team, job_id)

async def _send_error_message_to_user(chat_id: int):
    """Вспомогательная асинхронная функция для отправки сообщения об ошибке."""
    try:
        # Создаем временный бот для отправки сообщения
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        await bot.send_message(
            chat_id=chat_id,
            text=ERROR_MESSAGE,
            parse_mode="HTML"
        )
        await bot.session.close()
    except Exception as send_error:
        logger.error(f"Ошибка при отправке сообщения об ошибке пользователю: {send_error}")

# --- КОНЕЦ ФУНКЦИИ ДЛЯ ВЫЗОВА ИЗ RQ ---

if __name__ == "__main__":
    # Запуск основной функции
    asyncio.run(main())