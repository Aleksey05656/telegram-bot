# config.py
"""Конфигурация приложения с использованием Pydantic Settings v2.
Параметры загружаются из переменных окружения."""
import os
from typing import Optional, Dict
from datetime import datetime
from pydantic import field_validator, computed_field, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Класс конфигурации приложения.
    Загружает параметры из переменных окружения и .env файла."""
    # --- API Keys ---
    TELEGRAM_BOT_TOKEN: str
    SPORTMONKS_API_KEY: str
    ODDS_API_KEY: str  # Обязательное поле, без значения по умолчанию

    # --- Infrastructure ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = Field(default=0, ge=0, le=15)  # Номер БД Redis: 0–15

    # Асинхронный URL для базы данных (используется в приложении)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@postgres:5432/sports"

    # --- ML Models ---
    XGBOOST_MODEL_PATH: str = "ml/models/xgboost_model.pkl"
    POISSON_MODEL_PATH: str = "ml/models/poisson_model.pkl"

    # === НОВЫЕ ПАРАМЕТРЫ ДЛЯ ЭТАПА 1 ===
    MODELS_DIR: str = "models"
    MODEL_VERSION: Optional[str] = None  # если None — генерируется по MODEL_VERSION_FORMAT
    MODEL_VERSION_FORMAT: str = "%Y%m%d%H%M"  # точность до минут по умолчанию; можно сменить в .env
    CALIBRATION_METHOD: str = "platt"  # 'platt' | 'isotonic' | 'beta'
    CV_N_SPLITS: int = 6
    CV_GAP_DAYS: int = 0
    CV_MIN_TRAIN_DAYS: int = 120
    TIME_DECAY_HALFLIFE_DAYS: int = 180
    # === КОНЕЦ НОВЫХ ПАРАМЕТРОВ ===

    # --- Application Settings ---
    LOG_LEVEL: str = "INFO"
    DEBUG_MODE: bool = False
    APP_ENV: str = "development"

    # --- Кэширование ---
    CACHE_VERSION: str = "v3"  # Обновлять при изменении логики или фич

    # TTL для различных типов данных кэша (в секундах)
    TTL: Dict[str, int] = {
        "fixtures_base": 6 * 3600,      # 6 часов
        "table_base": 24 * 3600,        # 24 часа
        "form_slow": 24 * 3600,         # 24 часа
        "weather_fast": 15 * 60,        # 15 минут
        "lineups_fast": 90,             # 90 секунд
        "injuries_fast": 120,           # 2 минуты
    }

    # Параметры расчёта уверенности
    CONFIDENCE: Dict[str, float] = {
        "missing_penalty_alpha": 0.2,
        "freshness_penalty_alpha": 0.15,
    }

    # Флаги моделей
    MODEL_FLAGS: Dict[str, bool] = {
        "enable_bivariate_poisson": True,
        "enable_calibration": True,
    }

    # --- Динамические поля ---
    @computed_field  # Генерируется на основе других полей
    @property
    def REDIS_URL(self) -> str:
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Валидация ---
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'LOG_LEVEL must be one of {allowed_levels}')
        return v.upper()

    @field_validator('CALIBRATION_METHOD')
    @classmethod
    def validate_calibration_method(cls, v):
        allowed_methods = ['platt', 'isotonic', 'beta']
        if v not in allowed_methods:
            raise ValueError(f'CALIBRATION_METHOD must be one of {allowed_methods}')
        return v

    @field_validator('CACHE_VERSION')
    @classmethod
    def validate_cache_version(cls, v: str) -> str:
        if not v.startswith("v"):
            raise ValueError("CACHE_VERSION должен начинаться с 'v'")
        try:
            version_num = int(v[1:])
            if version_num < 0:
                raise ValueError("Версия кэша должна быть положительной")
        except ValueError:
            raise ValueError("После 'v' должна следовать цифра")
        return v

    @field_validator('MODEL_VERSION')
    @classmethod
    def set_default_model_version(cls, v):
        if v is None:
            # формат можно задать через .env -> MODEL_VERSION_FORMAT
            fmt = getattr(cls, 'MODEL_VERSION_FORMAT', "%Y%m%d%H%M")
            try:
                return f"v{datetime.now().strftime(fmt)}"
            except Exception:
                # на случай некорректного формата — запасной вариант по дате
                return f"v{datetime.now().strftime('%Y%m%d')}"
        return v

    # --- Конфигурация Pydantic ---
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Игнорировать лишние переменные окружения
    }

def get_settings() -> Settings:
    """Получить актуальные настройки, загрузив их из .env"""
    # Явно валидируем окружение/файл .env (pydantic-settings v2)
    return Settings.model_validate_env()

# Убираем глобальный settings — он может быть устаревшим
# и одновременно создаём back-compat алиасы для остального кода.
settings = get_settings()

# --- Back-compat aliases (глобали, которые ожидает существующий код) ---
# CACHE_VERSION как строка:
CACHE_VERSION: str = settings.CACHE_VERSION
# TTL / CONFIDENCE / MODEL_FLAGS как dict-объекты:
try:
    TTL = settings.TTL.model_dump()
except Exception:
    TTL = dict(settings.TTL)
try:
    CONFIDENCE = settings.CONFIDENCE.model_dump()
except Exception:
    CONFIDENCE = dict(settings.CONFIDENCE)
try:
    MODEL_FLAGS = settings.MODEL_FLAGS.model_dump()
except Exception:
    MODEL_FLAGS = dict(settings.MODEL_FLAGS)
