# config.py
"""Конфигурация приложения с использованием Pydantic Settings v2.
Параметры загружаются из переменных окружения."""
from datetime import datetime
from pathlib import Path

from pydantic import Field, computed_field, field_validator

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Класс конфигурации приложения.
    Загружает параметры из переменных окружения и .env файла."""

    # --- API Keys ---
    TELEGRAM_BOT_TOKEN: str = ""
    SPORTMONKS_API_KEY: str = ""
    SPORTMONKS_API_TOKEN: str = ""
    SPORTMONKS_BASE_URL: str = "https://api.sportmonks.com/v3/football"
    SPORTMONKS_TIMEOUT_SEC: float = 10.0
    SPORTMONKS_RETRY_ATTEMPTS: int = 4
    SPORTMONKS_BACKOFF_BASE: float = 0.5
    SPORTMONKS_RPS_LIMIT: float = 3.0
    SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS: int = 7
    SPORTMONKS_LEAGUES_ALLOWLIST: str = ""
    SPORTMONKS_CACHE_TTL_SEC: int = 900
    ODDS_API_KEY: str = ""  # Обязательное поле, без значения по умолчанию
    ODDS_PROVIDERS: str = ""
    ODDS_PROVIDER_WEIGHTS: str = ""
    ODDS_PROVIDER: str = "dummy"
    ODDS_REFRESH_SEC: int = 300
    ODDS_RPS_LIMIT: float = 3.0
    ODDS_TIMEOUT_SEC: float = 8.0
    ODDS_RETRY_ATTEMPTS: int = 4
    ODDS_BACKOFF_BASE: float = 0.4
    ODDS_OVERROUND_METHOD: str = "proportional"
    ODDS_AGG_METHOD: str = "median"
    ODDS_SNAPSHOT_RETENTION_DAYS: int = 14
    RELIABILITY_DECAY: float = 0.9
    RELIABILITY_MIN_SCORE: float = 0.5
    RELIABILITY_MIN_COVERAGE: float = 0.6
    RELIABILITY_MAX_FRESHNESS_SEC: float = 600.0
    RELIAB_V2_ENABLE: bool = False
    RELIAB_DECAY: float = 0.92
    RELIAB_MIN_SAMPLES: int = 200
    RELIAB_SCOPE: str = "league_market"
    RELIAB_COMPONENT_WEIGHTS: str = "fresh:0.35,latency:0.15,stability:0.30,closing_bias:0.20"
    RELIAB_PRIOR_FRESH_ALPHA: float = 8.0
    RELIAB_PRIOR_FRESH_BETA: float = 2.0
    RELIAB_PRIOR_LATENCY_SHAPE: float = 3.0
    RELIAB_PRIOR_LATENCY_SCALE: float = 300.0
    RELIAB_STAB_Z_TOL: float = 1.0
    RELIAB_CLOSING_TOL_PCT: float = 0.75
    ANOMALY_Z_MAX: float = 3.0
    BEST_PRICE_MIN_SCORE: float = 0.6
    BEST_PRICE_LOOKBACK_MIN: int = 15
    VALUE_MIN_EDGE_PCT: float = 3.0
    VALUE_MIN_CONFIDENCE: float = 0.6
    VALUE_MAX_PICKS: int = 5
    VALUE_MARKETS: str = "1X2,OU_2_5,BTTS"
    VALUE_CONFIDENCE_METHOD: str = "none"
    VALUE_ALERT_COOLDOWN_MIN: int = 60
    VALUE_ALERT_QUIET_HOURS: str = "23:00-08:00"
    VALUE_ALERT_MIN_EDGE_DELTA: float = 0.7
    VALUE_ALERT_UPDATE_DELTA: float = 1.5
    VALUE_ALERT_MAX_UPDATES: int = 3
    VALUE_STALENESS_FAIL_MIN: int = 30
    CLV_WINDOW_BEFORE_KICKOFF_MIN: int = 120
    CLV_FAIL_THRESHOLD_PCT: float = -1.0
    SETTLEMENT_ENABLE: bool = True
    SETTLEMENT_POLL_MIN: int = 10
    SETTLEMENT_MAX_LAG_HOURS: int = 24
    PORTFOLIO_ROLLING_DAYS: int = 60
    BACKTEST_DAYS: int = 120
    BACKTEST_MIN_SAMPLES: int = 300
    BACKTEST_OPTIM_TARGET: str = "sharpe"
    BACKTEST_VALIDATION: str = "time_kfold"
    GATES_VALUE_SHARPE_WARN: float = 0.1
    GATES_VALUE_SHARPE_FAIL: float = 0.0
    ENABLE_VALUE_FEATURES: bool = False

    # --- Infrastructure ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = Field(default=0, ge=0, le=15)  # Номер БД Redis: 0–15

    # Асинхронный URL для базы данных (используется в приложении)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@postgres:5432/sports"
    DATABASE_URL_RO: str | None = None
    DATABASE_URL_R: str | None = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: float = 30.0
    DATABASE_CONNECT_TIMEOUT: float = 10.0
    DATABASE_STATEMENT_TIMEOUT_MS: int = 60_000
    DATABASE_SQLITE_TIMEOUT: float = 30.0
    DATABASE_ECHO: bool = False

    # --- ML Models ---
    XGBOOST_MODEL_PATH: str = "ml/models/xgboost_model.pkl"
    POISSON_MODEL_PATH: str = "ml/models/poisson_model.pkl"

    # === НОВЫЕ ПАРАМЕТРЫ ДЛЯ ЭТАПА 1 ===
    MODELS_DIR: str = "models"
    MODEL_VERSION: str | None = None  # если None — генерируется по MODEL_VERSION_FORMAT
    MODEL_VERSION_FORMAT: str = "%Y%m%d%H%M"  # точность до минут по умолчанию; можно сменить в .env
    CALIBRATION_METHOD: str = "platt"  # 'platt' | 'isotonic' | 'beta'
    CV_N_SPLITS: int = 6
    CV_GAP_DAYS: int = 0
    CV_MIN_TRAIN_DAYS: int = 120
    TIME_DECAY_HALFLIFE_DAYS: int = 180

    # --- Storage locations ---
    DATA_ROOT: str = "/data"
    DB_PATH: str = "/data/bot.sqlite3"
    MODEL_REGISTRY_PATH: str = "/data/artifacts"
    REPORTS_DIR: str = "/data/reports"
    LOG_DIR: str = "/data/logs"
    BACKUP_DIR: str = "/data/backups"
    BACKUP_KEEP: int = 10
    RUNTIME_LOCK_PATH: str = "/data/runtime.lock"
    ENABLE_HEALTH: bool = False
    HEALTH_HOST: str = "0.0.0.0"
    HEALTH_PORT: int = 8080
    ENABLE_METRICS: bool = False
    METRICS_PORT: int = 8000
    SHUTDOWN_TIMEOUT: float = 30.0

    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 8.0
    RETRY_BACKOFF: float = 2.0
    # === КОНЕЦ НОВЫХ ПАРАМЕТРОВ ===

    # --- Application Settings ---
    LOG_LEVEL: str = "INFO"
    DEBUG_MODE: bool = False
    APP_ENV: str = "development"
    APP_VERSION: str = "0.0.0"
    GIT_SHA: str = "dev"
    ENABLE_POLLING: bool = True
    ENABLE_SCHEDULER: bool = True
    STARTUP_DELAY_SEC: float = 0.0
    FAILSAFE_MODE: bool = False
    PAGINATION_PAGE_SIZE: int = 5
    CACHE_TTL_SECONDS: int = 120
    ADMIN_IDS: str = ""
    DIGEST_DEFAULT_TIME: str = "09:00"
    SHOW_DATA_STALENESS: int = 0

    # --- Observability ---
    SENTRY_DSN: str | None = None
    PROMETHEUS_PORT: int = 8008

    # --- Кэширование ---
    CACHE_VERSION: str = "v3"  # Обновлять при изменении логики или фич

    # TTL для различных типов данных кэша (в секундах)
    TTL: dict[str, int] = {
        "fixtures_base": 6 * 3600,  # 6 часов
        "table_base": 24 * 3600,  # 24 часа
        "form_slow": 24 * 3600,  # 24 часа
        "weather_fast": 15 * 60,  # 15 минут
        "lineups_fast": 90,  # 90 секунд
        "injuries_fast": 120,  # 2 минуты
    }

    # Параметры расчёта уверенности
    CONFIDENCE: dict[str, float] = {
        "missing_penalty_alpha": 0.2,
        "freshness_penalty_alpha": 0.15,
    }

    # Флаги моделей
    MODEL_FLAGS: dict[str, bool] = {
        "enable_bivariate_poisson": True,
        "enable_calibration": True,
    }

    # --- Simulation ---
    SIM_RHO: float = 0.1
    SIM_N: int = 10000
    SIM_CHUNK: int = 100000
    SIM_SEED: int = 20240920

    # --- Worker coordination ---
    PREDICTION_LOCK_TIMEOUT: float = 60.0
    PREDICTION_LOCK_BLOCKING_TIMEOUT: float = 5.0

    # --- Diagnostics orchestration ---
    DIAG_SCHEDULE_CRON: str = "0 6 * * *"
    DIAG_ON_START: bool = True
    DIAG_MAX_RUNTIME_MIN: int = 25
    REPORTS_IMG_FORMAT: str = "svg"
    DIAG_HISTORY_KEEP: int = 60
    ALERTS_ENABLED: bool = True
    ALERTS_CHAT_ID: str | None = None
    ALERTS_MIN_LEVEL: str = "WARN"
    AUTO_REF_UPDATE: str = "off"
    SM_FRESHNESS_WARN_HOURS: int = 12
    SM_FRESHNESS_FAIL_HOURS: int = 48

    # --- Динамические поля ---
    @computed_field  # Генерируется на основе других полей
    @property
    def REDIS_URL(self) -> str:
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Валидация ---
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v.upper()

    @field_validator("CALIBRATION_METHOD")
    @classmethod
    def validate_calibration_method(cls, v):
        allowed_methods = ["platt", "isotonic", "beta"]
        if v not in allowed_methods:
            raise ValueError(f"CALIBRATION_METHOD must be one of {allowed_methods}")
        return v

    @field_validator("VALUE_CONFIDENCE_METHOD")
    @classmethod
    def validate_value_conf_method(cls, v: str) -> str:
        allowed_methods = {"mc_var", "none"}
        if v not in allowed_methods:
            raise ValueError(f"VALUE_CONFIDENCE_METHOD must be one of {sorted(allowed_methods)}")
        return v

    @field_validator("BACKTEST_VALIDATION")
    @classmethod
    def validate_backtest_validation(cls, v: str) -> str:
        allowed = {"time_kfold", "walk_forward"}
        if v not in allowed:
            raise ValueError(f"BACKTEST_VALIDATION must be one of {sorted(allowed)}")
        return v

    @field_validator("BACKTEST_OPTIM_TARGET")
    @classmethod
    def validate_backtest_target(cls, v: str) -> str:
        allowed = {"sharpe", "hit", "loggain"}
        if v not in allowed:
            raise ValueError(f"BACKTEST_OPTIM_TARGET must be one of {sorted(allowed)}")
        return v

    @field_validator("HEALTH_PORT")
    @classmethod
    def validate_health_port(cls, v: int) -> int:
        if v <= 0 or v > 65535:
            raise ValueError("HEALTH_PORT must be between 1 and 65535")
        return v

    @field_validator("METRICS_PORT")
    @classmethod
    def validate_metrics_port(cls, v: int) -> int:
        if v <= 0 or v > 65535:
            raise ValueError("METRICS_PORT must be between 1 and 65535")
        return v

    @field_validator("REPORTS_IMG_FORMAT")
    @classmethod
    def validate_reports_img_format(cls, v: str) -> str:
        allowed = {"svg", "png"}
        if v not in allowed:
            raise ValueError(f"REPORTS_IMG_FORMAT must be one of {sorted(allowed)}")
        return v

    @field_validator("DIAG_HISTORY_KEEP", "DIAG_MAX_RUNTIME_MIN")
    @classmethod
    def validate_positive_ints(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @field_validator("ALERTS_MIN_LEVEL")
    @classmethod
    def validate_alerts_level(cls, v: str) -> str:
        allowed = {"WARN", "FAIL"}
        if v not in allowed:
            raise ValueError("ALERTS_MIN_LEVEL must be WARN or FAIL")
        return v

    @field_validator("AUTO_REF_UPDATE")
    @classmethod
    def validate_auto_ref_update(cls, v: str) -> str:
        allowed = {"off", "approved"}
        if v not in allowed:
            raise ValueError("AUTO_REF_UPDATE must be 'off' or 'approved'")
        return v

    @field_validator("RETRY_ATTEMPTS")
    @classmethod
    def validate_retry_attempts(cls, v: int) -> int:
        if v < 0:
            raise ValueError("RETRY_ATTEMPTS must be >= 0")
        return v

    @field_validator("RETRY_DELAY", "RETRY_MAX_DELAY", "RETRY_BACKOFF")
    @classmethod
    def validate_retry_numbers(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Retry timing parameters must be positive")
        return v

    @field_validator("PAGINATION_PAGE_SIZE")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("PAGINATION_PAGE_SIZE must be positive")
        return v

    @field_validator("CACHE_TTL_SECONDS")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("CACHE_TTL_SECONDS must be positive")
        return v

    @field_validator("DIGEST_DEFAULT_TIME")
    @classmethod
    def validate_digest_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("DIGEST_DEFAULT_TIME must be HH:MM")
        hour, minute = parts
        if not hour.isdigit() or not minute.isdigit():
            raise ValueError("DIGEST_DEFAULT_TIME must be HH:MM")
        hour_i = int(hour)
        minute_i = int(minute)
        if not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
            raise ValueError("DIGEST_DEFAULT_TIME must be valid time")
        return f"{hour_i:02d}:{minute_i:02d}"

    @field_validator("CACHE_VERSION")
    @classmethod
    def validate_cache_version(cls, v: str) -> str:
        if not v.startswith("v"):
            raise ValueError("CACHE_VERSION должен начинаться с 'v'")
        try:
            version_num = int(v[1:])
            if version_num < 0:
                raise ValueError("Версия кэша должна быть положительной")
        except ValueError as e:
            raise ValueError("После 'v' должна следовать цифра") from e
        return v

    @field_validator("MODEL_VERSION")
    @classmethod
    def set_default_model_version(cls, v):
        if v is None:
            # формат можно задать через .env -> MODEL_VERSION_FORMAT
            fmt = getattr(cls, "MODEL_VERSION_FORMAT", "%Y%m%d%H%M")
            try:
                return f"v{datetime.now().strftime(fmt)}"
            except Exception:
                # на случай некорректного формата — запасной вариант по дате
                return f"v{datetime.now().strftime('%Y%m%d')}"
        return v

    @field_validator("DB_PATH")
    @classmethod
    def ensure_db_dir(cls, v: str) -> str:
        path = Path(v)
        if not path.is_absolute():
            path = Path(cls.DATA_ROOT) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator("MODEL_REGISTRY_PATH", "REPORTS_DIR", "LOG_DIR", "BACKUP_DIR")
    @classmethod
    def ensure_data_dir(cls, v: str):
        base = Path(v)
        if not base.is_absolute():
            base = Path(cls.DATA_ROOT) / base
        base.mkdir(parents=True, exist_ok=True)
        return str(base)

    @field_validator("BACKUP_KEEP")
    @classmethod
    def validate_backup_keep(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("BACKUP_KEEP must be positive")
        return v

    @field_validator("RUNTIME_LOCK_PATH")
    @classmethod
    def ensure_lock_path(cls, v: str) -> str:
        path = Path(v)
        if not path.is_absolute():
            path = Path(cls.DATA_ROOT) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # --- Конфигурация Pydantic ---
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",  # Игнорировать лишние переменные окружения
    }


def get_settings() -> Settings:
    """Получить актуальные настройки, загрузив их из .env"""
    # Явно валидируем окружение/файл .env (pydantic-settings v2)
    s = Settings()
    object.__setattr__(s, "sportmonks_api_key", s.SPORTMONKS_API_KEY)
    return s


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
