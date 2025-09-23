# logger.py
# Настройка логирования с использованием loguru и JSON.
"""Модуль для настройки логирования и отслеживания деградации модели."""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from config import settings

# Создаем директорию для логов если её нет
log_dir = Path(settings.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)

# Глобальная переменная для отслеживания деградации модели
_model_degradation_threshold = 0.1  # Порог деградации 10%
_model_performance_baseline = None  # Базовое значение производительности
_model_metrics_history = []  # История метрик модели


def set_model_degradation_threshold(threshold: float):
    """Установка порога деградации модели.

    Args:
        threshold (float): Порог деградации (0-1)
    """
    global _model_degradation_threshold
    _model_degradation_threshold = max(0.0, min(1.0, threshold))
    logger.info(f"Установлен порог деградации модели: {threshold:.2%}")


def set_model_performance_baseline(baseline: float):
    """Установка базового значения производительности модели.

    Args:
        baseline (float): Базовое значение производительности
    """
    global _model_performance_baseline
    _model_performance_baseline = baseline
    logger.info(
        f"Установлено базовое значение производительности модели: {baseline:.4f}"
    )


def add_model_metrics(metrics: dict[str, Any]):
    """Добавление метрик модели в историю.

    Args:
        metrics (Dict[str, Any]): Метрики модели
    """
    global _model_metrics_history
    _model_metrics_history.append(
        {"timestamp": datetime.now().isoformat(), "metrics": metrics}
    )
    # Ограничиваем историю последними 100 записями
    _model_metrics_history = _model_metrics_history[-100:]


def get_model_metrics_history() -> list:
    """Получение истории метрик модели.

    Returns:
        list: История метрик модели
    """
    global _model_metrics_history
    return _model_metrics_history.copy()


def check_model_degradation(
    current_metrics: dict[str, float],
    baseline_metrics: dict[str, float] = None,
    threshold_percent: float = 10.0,
) -> bool:
    """
    Проверка деградации модели по сравнению с базовыми метриками.

    Args:
        current_metrics (Dict[str, float]): Текущие метрики модели
        baseline_metrics (Dict[str, float]): Базовые метрики модели
        threshold_percent (float): Порог деградации в процентах

    Returns:
        bool: True если обнаружена деградация
    """
    global _model_performance_baseline, _model_degradation_threshold, _model_metrics_history
    try:
        # Валидация входных данных
        if not isinstance(current_metrics, dict):
            logger.error("current_metrics должен быть словарем")
            return False

        # Используем переданные базовые метрики или глобальные
        if baseline_metrics is None:
            baseline_metrics = _model_performance_baseline
        if not baseline_metrics:
            logger.debug("Базовые метрики не установлены, пропуск проверки деградации")
            return False

        # Проверяем, что базовые метрики тоже словарь
        if not isinstance(baseline_metrics, dict):
            logger.error("baseline_metrics должен быть словарем")
            return False

        degraded = False
        degradation_details = []

        # Проверяем каждую метрику
        for metric_name, current_value in current_metrics.items():
            if metric_name in baseline_metrics:
                baseline_value = baseline_metrics[metric_name]

                # Проверяем, что значения числовые
                if not isinstance(current_value, int | float) or not isinstance(
                    baseline_value, int | float
                ):
                    logger.warning(
                        f"Метрика {metric_name} имеет некорректный тип данных"
                    )
                    continue

                # Проверка на деление на ноль
                if baseline_value == 0:
                    logger.warning(
                        f"Невозможно рассчитать изменение для метрики {metric_name}, базовое значение равно 0"
                    )
                    continue

                if metric_name in ["logloss", "brier_score"]:
                    # Для метрик, где меньше - лучше
                    change_percent = (
                        (current_value - baseline_value) / abs(baseline_value)
                    ) * 100
                    is_degraded = change_percent > threshold_percent
                else:
                    # Для метрик, где больше - лучше (slope, intercept)
                    change_percent = (
                        (baseline_value - current_value) / abs(baseline_value)
                    ) * 100
                    is_degraded = change_percent > threshold_percent

                if is_degraded:
                    degraded = True
                    degradation_details.append(
                        f"{metric_name}: {baseline_value:.4f} -> {current_value:.4f} "
                        f"({change_percent:+.2f}%)"
                    )
                    logger.warning(
                        f"⚠️ Деградация модели по метрике {metric_name}: "
                        f"{baseline_value:.4f} -> {current_value:.4f} "
                        f"({change_percent:+.2f}%)"
                    )

        if degraded:
            logger.warning(
                f"⚠️ Обнаружена деградация модели! Порог: {threshold_percent}%. "
                f"Детали: {'; '.join(degradation_details)}"
            )
            # Отправляем предупреждение в Sentry (если интеграция есть)
            try:
                import sentry_sdk

                sentry_sdk.capture_message(
                    f"Model degradation detected: {'; '.join(degradation_details)}",
                    level="warning",
                )
            except ImportError:
                logger.debug("Sentry не установлен, пропуск отправки уведомления")
            except Exception as sentry_error:
                logger.error(
                    f"Ошибка при отправке уведомления в Sentry: {sentry_error}"
                )
        else:
            logger.info("✅ Модель не демонстрирует значительной деградации")

        return degraded
    except Exception as e:
        logger.error(f"Ошибка при проверке деградации модели: {e}", exc_info=True)
        return False


# Класс для управления ротацией логов
class JsonLogFile:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.current_date = None
        self.file_handle = None

    def write(self, message: str):
        """Записывает сообщение в файл с учетом даты."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Если дата изменилась или файл не открыт, открываем новый файл
        if self.current_date != current_date or self.file_handle is None:
            if self.file_handle:
                self.file_handle.close()
            self.current_date = current_date
            filename = self.base_path / f"app_{current_date}.json.log"
            self.file_handle = open(filename, "a", encoding="utf-8")
        self.file_handle.write(message)
        self.file_handle.flush()

    def close(self):
        """Закрывает файл."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


# Создаем экземпляр для JSON логов
json_log_file = JsonLogFile(log_dir)


# Функция для создания JSON логов
def json_sink(message):
    """Функция для записи логов в JSON формате."""
    record = message.record
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }
    # Добавляем exception info, если есть
    if record["exception"]:
        log_entry["exception"] = str(record["exception"])
    # Добавляем любые extra поля
    for key, value in record.get("extra", {}).items():
        if key not in [
            "time",
            "level",
            "message",
            "name",
            "function",
            "line",
            "exception",
        ]:
            log_entry[key] = value
    # Записываем в файл
    json_log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# - Настройка Loguru -
# Удаляем стандартные обработчики
logger.remove()

# Добавляем обработчик для файла с JSON форматированием
logger.add(sink=json_sink, level="DEBUG", backtrace=True, diagnose=True)

# Добавляем обработчик для консоли
logger.add(
    sink=sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>",
    level=settings.LOG_LEVEL,
    backtrace=True,
    diagnose=True,
)

# Экспорт logger для использования в других модулях
__all__ = [
    "logger",
    "set_model_degradation_threshold",
    "set_model_performance_baseline",
    "add_model_metrics",
    "get_model_metrics_history",
    "check_model_degradation",
]
