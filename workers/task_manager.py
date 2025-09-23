# workers/task_manager.py
"""Менеджер задач для обработки прогнозов в фоне."""
import json
from datetime import datetime, timedelta
from typing import Any

import redis
from redis import Redis
from rq import Queue
from rq.job import Job

from config import settings  # Импортируем settings
from app.metrics import set_queue_depth
from logger import logger
from ml.models.poisson_regression_model import poisson_regression_model


class TaskManager:
    """Класс для управления задачами RQ."""

    def __init__(self):
        """Инициализация менеджера задач."""
        self.redis_conn: Redis | None = None
        self.prediction_queue: Queue | None = None
        self.retraining_queue: Queue | None = None  # Новая очередь для переобучения
        logger.debug("TaskManager: Инициализация экземпляра...")

    def _update_depth_metric(self) -> None:
        total = 0
        for q in (self.prediction_queue, self.retraining_queue):
            if q is None:
                continue
            try:
                total += len(q)
            except Exception:
                continue
        set_queue_depth(total)

    async def initialize(self):
        """Асинхронная инициализация подключения к Redis и очередей."""
        try:
            logger.info("TaskManager: Начало инициализации...")
            # Проверяем, не инициализирован ли уже менеджер
            if self.redis_conn is not None:
                logger.warning("TaskManager: Уже инициализирован, пропускаем инициализацию")
                return

            # Подключение к Redis
            logger.debug(f"TaskManager: Подключение к Redis по URL: {settings.REDIS_URL}")
            self.redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)

            # Проверка соединения
            self.redis_conn.ping()
            logger.info("✅ Подключение к Redis для RQ установлено")

            # Создаем очередь RQ с именем 'predictions'
            logger.debug("TaskManager: Создание очереди 'predictions'...")
            self.prediction_queue = Queue(
                "predictions", connection=self.redis_conn, default_timeout=600
            )  # 10 минут

            # Создаем очередь RQ для переобучения
            logger.debug("TaskManager: Создание очереди 'retraining'...")
            self.retraining_queue = Queue(
                "retraining", connection=self.redis_conn, default_timeout=7200
            )  # 2 часа

            logger.debug("✅ Очереди 'predictions' и 'retraining' успешно созданы")
            logger.info("✅ TaskManager успешно инициализирован")
            self._update_depth_metric()

        except redis.ConnectionError as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}", exc_info=True)
            self.redis_conn = None
            self.prediction_queue = None
            self.retraining_queue = None
            self._update_depth_metric()
        except Exception as e:  # Этот обработчик теперь поймает AttributeError и другие
            logger.error(
                f"❌ Неизвестная ошибка при инициализации TaskManager: {e}",
                exc_info=True,
            )
            self.redis_conn = None
            self.prediction_queue = None
            self.retraining_queue = None

    def enqueue_prediction(
        self,
        chat_id: int,
        home_team: str,
        away_team: str,
        job_id: str,
        priority: str = "normal",
    ) -> Job | None:
        """Постановка задачи прогнозирования в очередь.
        Args:
            chat_id (int): ID чата Telegram.
            home_team (str): Название домашней команды.
            away_team (str): Название гостевой команды.
            job_id (str): Уникальный идентификатор задачи.
            priority (str): Приоритет задачи ('high', 'normal', 'low').
        Returns:
            Optional[Job]: Объект задачи RQ или None в случае ошибки.
        """
        try:
            logger.debug(
                f"[{job_id}] enqueue_prediction: Начало постановки задачи в очередь для {home_team} vs {away_team} с приоритетом {priority}"
            )
            # - ДИАГНОСТИКА: Проверка инициализации -
            if not self.redis_conn:
                logger.error(f"[{job_id}] enqueue_prediction: Redis connection не инициализирован!")
                return None
            if not self.prediction_queue:
                logger.error(
                    f"[{job_id}] enqueue_prediction: Очередь prediction_queue не инициализирована!"
                )
                return None
            logger.debug(
                f"[{job_id}] enqueue_prediction: Redis и очередь инициализированы корректно."
            )
            # - КОНЕЦ ДИАГНОСТИКИ -
            # Импортируем функцию обработки непосредственно здесь, чтобы избежать циклических импортов
            from workers.prediction_worker import process_prediction

            logger.debug(f"[{job_id}] enqueue_prediction: Постановка задачи в очередь RQ...")
            # Ставим задачу в очередь
            job_obj = self.prediction_queue.enqueue(
                process_prediction,
                chat_id,
                home_team,
                away_team,
                job_id,
                job_id=job_id,  # Используем job_id как ID задачи в RQ
                job_timeout="10m",  # Таймаут задачи 10 минут
                ttl=86400,  # Время жизни задачи в очереди 1 день
                result_ttl=86400,  # Время жизни результата 1 день
                meta={"priority": priority, "type": "prediction"},
            )
            logger.info(f"[{job_id}] ✅ Задача прогнозирования успешно поставлена в очередь")
            self._update_depth_metric()
            return job_obj
        except Exception as e:
            logger.error(
                f"[{job_id}] ❌ Ошибка при постановке задачи прогнозирования в очередь: {e}",
                exc_info=True,
            )
            return None

    def enqueue_retraining(
        self, reason: str = "scheduled", season_id: int | None = None
    ) -> Job | None:
        """Постановка задачи переобучения модели в очередь.
        Args:
            reason (str): Причина переобучения ('scheduled', 'new_matches', 'model_outdated', 'distribution_shift')
            season_id (Optional[int]): ID сезона для обучения (если не указан, используется по умолчанию)
        Returns:
            Optional[Job]: Объект задачи RQ или None в случае ошибки.
        """
        try:
            logger.debug(
                f"enqueue_retraining: Начало постановки задачи переобучения (причина: {reason})"
            )
            # - ДИАГНОСТИКА: Проверка инициализации -
            if not self.redis_conn:
                logger.error("enqueue_retraining: Redis connection не инициализирован!")
                return None
            if not self.retraining_queue:
                logger.error("enqueue_retraining: Очередь retraining_queue не инициализирована!")
                return None
            logger.debug("enqueue_retraining: Redis и очередь инициализированы корректно.")
            # - КОНЕЦ ДИАГНОСТИКИ -
            # Импортируем функцию обучения непосредственно здесь
            from scripts.train_model import train_and_persist

            logger.debug("enqueue_retraining: Постановка задачи переобучения в очередь RQ...")
            # Ставим задачу переобучения в очередь
            job_obj = self.retraining_queue.enqueue(
                train_and_persist,
                season_id,
                job_id=f"retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}",  # Уникальный ID задачи
                job_timeout="2h",  # Таймаут задачи 2 часа
                ttl=86400,  # Время жизни задачи в очереди 1 день
                result_ttl=86400,  # Время жизни результата 1 день
                meta={
                    "reason": reason,
                    "type": "retraining",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            logger.info(f"✅ Задача переобучения успешно поставлена в очередь (причина: {reason})")
            self._update_depth_metric()
            return job_obj
        except Exception as e:
            logger.error(
                f"❌ Ошибка при постановке задачи переобучения в очередь: {e}",
                exc_info=True,
            )
            return None

    # --- Maintenance utilities ---
    def clear_all(self) -> int:
        """Очистить все очереди. Возвращает количество удалённых задач."""
        removed = 0
        for q in (self.prediction_queue, self.retraining_queue):
            if not q:
                continue
            try:
                removed += q.count  # type: ignore[attr-defined]
                q.empty()
            except Exception:
                continue
        self._update_depth_metric()
        return removed

    def cleanup(self, days: int = 7) -> int:
        """Удалить задачи старше заданного количества дней."""
        if not self.redis_conn:
            return 0
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        for q in (self.prediction_queue, self.retraining_queue):
            if not q:
                continue
            for job_id in list(q.job_ids):  # type: ignore[attr-defined]
                try:
                    job = q.fetch_job(job_id)
                    if job and getattr(job, "enqueued_at", None) and job.enqueued_at < cutoff:
                        job.delete()
                        removed += 1
                except Exception:
                    continue
        return removed

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Получение статуса задачи по её ID.
        Args:
            job_id (str): ID задачи.
        Returns:
            Optional[Dict[str, Any]]: Словарь со статусом задачи или None в случае ошибки.
        """
        # Проверка инициализации
        if not self.redis_conn:
            logger.warning("Попытка получить статус задачи при неинициализированном TaskManager")
            return None
        try:
            # Получаем задачу по ID
            job = Job.fetch(job_id, connection=self.redis_conn)
            # Формируем словарь со статусом
            return {
                "id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                "meta": job.meta,
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статуса задачи {job_id}: {e}")
            return None

    def cancel_job(self, job_id: str) -> bool:
        """Отмена задачи по её ID.
        Args:
            job_id (str): ID задачи.
        Returns:
            bool: True если задача успешно отменена, иначе False.
        """
        # Проверка инициализации
        if not self.redis_conn:
            logger.warning("Попытка отменить задачу при неинициализированном TaskManager")
            return False
        try:
            # Получаем задачу по ID
            job = Job.fetch(job_id, connection=self.redis_conn)
            # Отменяем задачу
            job.cancel()
            logger.info(f"Задача {job_id} успешно отменена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отмене задачи {job_id}: {e}")
            return False

    def check_and_trigger_retraining(
        self, new_matches_count: int = 0, force_check: bool = False
    ) -> bool:
        """
        Проверка условий для триггера переобучения и запуск при необходимости.
        Args:
            new_matches_count (int): Количество новых матчей с последнего обучения
            force_check (bool): Принудительная проверка независимо от условий
        Returns:
            bool: True если переобучение было запущено, иначе False
        """
        try:
            # Проверка инициализации
            if not self.redis_conn or not self.retraining_queue:
                logger.warning("TaskManager не инициализирован для проверки условий переобучения")
                return False

            # Получаем настройки из конфигурации
            retrain_new_matches_threshold = getattr(settings, "RETRAIN_NEW_MATCHES_THRESHOLD", 50)
            retrain_model_age_threshold_days = getattr(
                settings, "RETRAIN_MODEL_AGE_THRESHOLD_DAYS", 7
            )

            logger.debug(
                f"Проверка условий переобучения: "
                f"новые матчи={new_matches_count}, "
                f"порог новых матчей={retrain_new_matches_threshold}, "
                f"порог возраста модели={retrain_model_age_threshold_days} дней"
            )

            should_retrain = False
            retrain_reason = ""

            # 1. Триггер: "накопилось X новых матчей"
            if new_matches_count >= retrain_new_matches_threshold:
                should_retrain = True
                retrain_reason = f"new_matches:{new_matches_count}"
                logger.info(
                    f"Триггер переобучения: накопилось {new_matches_count} новых матчей "
                    f"(порог {retrain_new_matches_threshold})"
                )

            # 2. Триггер: "устарела модель на Y дней"
            if not should_retrain or force_check:
                try:
                    # Проверяем возраст модели
                    if poisson_regression_model.is_model_outdated():
                        # Получаем дату последнего обновления модели
                        last_updated_str = poisson_regression_model.ratings.get("last_updated")
                        if last_updated_str:
                            last_updated = datetime.fromisoformat(last_updated_str)
                            model_age_days = (datetime.now() - last_updated).days
                            if model_age_days >= retrain_model_age_threshold_days:
                                should_retrain = True
                                retrain_reason = f"model_outdated:{model_age_days}days"
                                logger.info(
                                    f"Триггер переобучения: модель устарела на {model_age_days} дней "
                                    f"(порог {retrain_model_age_threshold_days} дней)"
                                )
                except Exception as age_check_error:
                    logger.error(f"Ошибка при проверке возраста модели: {age_check_error}")

            # 3. Триггер: "сдвиг дистрибуции" (заглушка - в реальной реализации здесь будет логика)
            if not should_retrain or force_check:
                # В реальной реализации здесь будет код для проверки сдвига дистрибуции
                # Например, сравнение текущих статистик с историческими
                distribution_shift_detected = False  # Заглушка
                if distribution_shift_detected:
                    should_retrain = True
                    retrain_reason = "distribution_shift"
                    logger.info("Триггер переобучения: обнаружен сдвиг дистрибуции")

            # 4. Принудительная проверка
            if force_check and not should_retrain:
                should_retrain = True
                retrain_reason = "forced"
                logger.info("Принудительный триггер переобучения")

            # Запуск переобучения если необходимо
            if should_retrain:
                logger.info(f"Начало переобучения модели (причина: {retrain_reason})")
                retrain_job = self.enqueue_retraining(reason=retrain_reason)
                if retrain_job:
                    logger.info(f"✅ Переобучение запущено успешно (задача: {retrain_job.id})")
                    return True
                else:
                    logger.error("❌ Не удалось запустить переобучение")
                    return False
            else:
                logger.debug("Условия для переобучения не выполнены")
                return False

        except Exception as e:
            logger.error(f"Ошибка при проверке условий переобучения: {e}", exc_info=True)
            return False

    def get_queue_stats(self) -> dict[str, Any]:
        """Получение статистики по очередям.
        Returns:
            Dict: Статистика очередей.
        """
        try:
            from rq.registry import (
                FailedJobRegistry,
                FinishedJobRegistry,
                StartedJobRegistry,
            )

            # Статистика для очереди прогнозов
            started_registry = StartedJobRegistry("predictions", connection=self.redis_conn)
            finished_registry = FinishedJobRegistry("predictions", connection=self.redis_conn)
            failed_registry = FailedJobRegistry("predictions", connection=self.redis_conn)
            # Статистика для очереди переобучения
            retrain_started_registry = StartedJobRegistry("retraining", connection=self.redis_conn)
            retrain_finished_registry = FinishedJobRegistry(
                "retraining", connection=self.redis_conn
            )
            retrain_failed_registry = FailedJobRegistry("retraining", connection=self.redis_conn)
            return {
                "predictions": {
                    "queued": len(self.prediction_queue) if self.prediction_queue else 0,
                    "started": len(started_registry),
                    "finished": len(finished_registry),
                    "failed": len(failed_registry),
                },
                "retraining": {
                    "queued": len(self.retraining_queue) if self.retraining_queue else 0,
                    "started": len(retrain_started_registry),
                    "finished": len(retrain_finished_registry),
                    "failed": len(retrain_failed_registry),
                },
                "last_updated": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики очереди: {e}")
            return {}

    def get_failed_jobs(
        self, queue_name: str = "predictions", limit: int = 10
    ) -> list[dict[str, Any]]:
        """Получение списка проваленных задач.
        Args:
            queue_name (str): Имя очереди ('predictions' или 'retraining')
            limit (int): Максимальное количество задач для возврата
        Returns:
            List[Dict]: Список проваленных задач.
        """
        try:
            from rq.registry import FailedJobRegistry

            registry = FailedJobRegistry(queue_name, connection=self.redis_conn)
            failed_jobs = []
            for job_id in registry.get_job_ids()[:limit]:
                try:
                    job = Job.fetch(job_id, connection=self.redis_conn)
                    failed_jobs.append(
                        {
                            "id": job.id,
                            "status": job.get_status(),
                            "created_at": job.created_at.isoformat() if job.created_at else None,
                            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                            "exc_info": job.exc_info,
                            "meta": job.meta,
                        }
                    )
                except Exception as job_error:
                    logger.error(
                        f"Ошибка при получении данных проваленной задачи {job_id}: {job_error}"
                    )
                    continue
            return failed_jobs
        except Exception as e:
            logger.error(f"Ошибка при получении проваленных задач: {e}")
            return []


# Создание экземпляра менеджера задач
task_manager = TaskManager()


# Экспорт основных функций для обратной совместимости
# (позволяет использовать task_manager.enqueue_prediction напрямую)
def enqueue_prediction(
    chat_id: int, home_team: str, away_team: str, job_id: str, priority: str = "normal"
) -> Job | None:
    """Совместимость с предыдущей версией."""
    return task_manager.enqueue_prediction(chat_id, home_team, away_team, job_id, priority)


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Совместимость с предыдущей версией."""
    return task_manager.get_job_status(job_id)


def cancel_job(job_id: str) -> bool:
    """Совместимость с предыдущей версией."""
    return task_manager.cancel_job(job_id)


def clear_all() -> int:
    """Очистить все очереди (совместимость)."""
    return task_manager.clear_all()


def cleanup(days: int = 7) -> int:
    """Очистить задачи старше N дней (совместимость)."""
    return task_manager.cleanup(days)


# Функции для CLI использования
def main():
    """Основная функция для CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Task Manager CLI")
    parser.add_argument(
        "action", choices=["stats", "cleanup", "failed"], help="Действие для выполнения"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Количество дней для хранения задач (для cleanup)",
    )

    # Инициализация TaskManager
    import asyncio

    asyncio.run(task_manager.initialize())

    args = parser.parse_args()

    if args.action == "stats":
        stats = task_manager.get_queue_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    elif args.action == "cleanup":
        removed = task_manager.cleanup(days=args.days)
        print(f"Удалено задач: {removed}")
    elif args.action == "failed":
        failed_jobs = task_manager.get_failed_jobs(limit=20)
        print(json.dumps(failed_jobs, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
