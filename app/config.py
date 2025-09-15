"""
@file: config.py
@description: Application settings via Pydantic v2
@dependencies: pydantic, pydantic-settings
@created: 2025-09-09
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseModel):
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
    retrain_cron: str | None = Field(default=None, alias="RETRAIN_CRON")
    sentry: SentrySettings = SentrySettings()
    prometheus: PrometheusSettings = PrometheusSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()


@lru_cache(1)
def get_settings() -> Settings:
    try:
        return Settings()  # auto-reads env via pydantic-settings v2
    except ValidationError:
        raise


def reset_settings_cache() -> None:
    """Сброс кэша настроек для тестов/смоуков при смене env."""
    try:
        get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
