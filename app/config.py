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
    enabled: bool = True
    requests: int = 60
    per_seconds: int = 60

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
