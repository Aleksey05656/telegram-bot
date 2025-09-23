"""
@file: config.py
@description: Application settings via Pydantic v2
@dependencies: pydantic, pydantic-settings
@created: 2025-09-09
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseModel):
    enabled: bool = False
    dsn: str | None = None
    environment: Literal["local", "dev", "stage", "prod"] = "local"


class PrometheusSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "/metrics"


class RateLimitSettings(BaseModel):
    enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    per_seconds: int = Field(default=60, alias="RATE_LIMIT_PER_SECONDS")

    @field_validator("requests", "per_seconds")
    @classmethod
    def positive(cls, v: int):
        if v <= 0:
            raise ValueError("must be > 0")
        return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )
    app_name: str = Field(default="ml-service", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    env: str = Field(default="local", alias="ENV")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    sportmonks_api_key: str = Field(default="", alias="SPORTMONKS_API_KEY")
    sportmonks_api_token: str = Field(default="", alias="SPORTMONKS_API_TOKEN")
    sportmonks_base_url: str = Field(
        default="https://api.sportmonks.com/v3/football", alias="SPORTMONKS_BASE_URL"
    )
    sportmonks_timeout_sec: float = Field(default=10.0, alias="SPORTMONKS_TIMEOUT_SEC")
    sportmonks_retry_attempts: int = Field(default=4, alias="SPORTMONKS_RETRY_ATTEMPTS")
    sportmonks_backoff_base: float = Field(default=0.5, alias="SPORTMONKS_BACKOFF_BASE")
    sportmonks_rps_limit: float = Field(default=3.0, alias="SPORTMONKS_RPS_LIMIT")
    sportmonks_default_timewindow_days: int = Field(
        default=7, alias="SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS"
    )
    sportmonks_leagues_allowlist: tuple[str, ...] = Field(
        default_factory=tuple, alias="SPORTMONKS_LEAGUES_ALLOWLIST"
    )
    sportmonks_cache_ttl_sec: int = Field(default=900, alias="SPORTMONKS_CACHE_TTL_SEC")
    show_data_staleness: bool = Field(default=False, alias="SHOW_DATA_STALENESS")
    sm_freshness_warn_hours: int = Field(default=12, alias="SM_FRESHNESS_WARN_HOURS")
    sm_freshness_fail_hours: int = Field(default=48, alias="SM_FRESHNESS_FAIL_HOURS")
    retrain_cron: str | None = Field(default=None, alias="RETRAIN_CRON")
    sentry: SentrySettings = SentrySettings()
    prometheus: PrometheusSettings = PrometheusSettings()
    git_sha: str = Field(default="dev", alias="GIT_SHA")
    app_version: str = Field(default="0.0.0", alias="APP_VERSION")
    rate_limit: RateLimitSettings = RateLimitSettings()
    sim_rho: float = Field(default=0.1, alias="SIM_RHO")
    sim_n: int = Field(default=10000, alias="SIM_N")
    sim_chunk: int = Field(default=100000, alias="SIM_CHUNK")

    @field_validator("sportmonks_leagues_allowlist", mode="before")
    @classmethod
    def _split_allowlist(cls, value: tuple[str, ...] | str | None) -> tuple[str, ...]:
        if value is None:
            return tuple()
        if isinstance(value, tuple):
            return value
        if not value:
            return tuple()
        return tuple(item.strip() for item in value.split(",") if item.strip())


@lru_cache(1)
def get_settings() -> Settings:
    return Settings()  # auto-reads env via pydantic-settings v2


def reset_settings_cache() -> None:
    """Сброс кэша настроек для тестов/смоуков при смене env."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
