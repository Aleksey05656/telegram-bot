"""
@file: config.py
@description: Application settings via Pydantic v2
@dependencies: pydantic, pydantic-settings
@created: 2025-09-09
"""

from __future__ import annotations

import logging
import os
import urllib.parse as _u
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentrySettings(BaseModel):
    enabled: bool = False
    dsn: str | None = None
    environment: Literal["local", "dev", "stage", "prod"] = "local"


class PrometheusSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "/metrics"


class OddsSettings(BaseModel):
    provider: Literal["dummy", "csv", "http"] = "dummy"
    refresh_sec: int = 300
    rps_limit: float = 3.0
    timeout_sec: float = 8.0
    retry_attempts: int = 4
    backoff_base: float = 0.4
    overround_method: Literal["proportional", "shin"] = "proportional"


class ValueSettings(BaseModel):
    min_edge_pct: float = 3.0
    min_confidence: float = 0.6
    max_picks: int = 5
    markets: tuple[str, ...] = ("1X2", "OU_2_5", "BTTS")


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
    canary: bool = Field(default=False, alias="CANARY")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    sportmonks_api_key: str = Field(default="", alias="SPORTMONKS_API_KEY")
    sportmonks_api_token: str = Field(default="", alias="SPORTMONKS_API_TOKEN")
    sportmonks_token: str = Field(default="", alias="SPORTMONKS_TOKEN")
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
    database_url_rw: str = Field(default="", alias="DATABASE_URL")
    database_url_ro: str = Field(default="", alias="DATABASE_URL_RO")
    database_url_rr: str = Field(default="", alias="DATABASE_URL_R")
    pg_host_default: str = Field(default="", alias="PGHOST")
    pg_host_rw: str = Field(default="", alias="PGHOST_RW")
    pg_host_ro: str = Field(default="", alias="PGHOST_RO")
    pg_host_rr: str = Field(default="", alias="PGHOST_RR")
    pg_port: int = Field(default=5432, alias="PGPORT")
    pg_database: str = Field(default="", alias="PGDATABASE")
    pg_user: str = Field(default="", alias="PGUSER")
    pg_password: str = Field(default="", alias="PGPASSWORD")
    redis_url: str = Field(default="", alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    enable_metrics: bool = Field(default=False, alias="ENABLE_METRICS")
    metrics_port: int = Field(default=8000, alias="METRICS_PORT")
    rate_limit: RateLimitSettings = RateLimitSettings()
    sim_rho: float = Field(default=0.1, alias="SIM_RHO")
    sim_n: int = Field(default=10000, alias="SIM_N")
    sim_chunk: int = Field(default=100000, alias="SIM_CHUNK")
    odds_provider: Literal["dummy", "csv", "http"] = Field(
        default="dummy", alias="ODDS_PROVIDER"
    )
    odds_refresh_sec: int = Field(default=300, alias="ODDS_REFRESH_SEC")
    odds_rps_limit: float = Field(default=3.0, alias="ODDS_RPS_LIMIT")
    odds_timeout_sec: float = Field(default=8.0, alias="ODDS_TIMEOUT_SEC")
    odds_retry_attempts: int = Field(default=4, alias="ODDS_RETRY_ATTEMPTS")
    odds_backoff_base: float = Field(default=0.4, alias="ODDS_BACKOFF_BASE")
    odds_overround_method: Literal["proportional", "shin"] = Field(
        default="proportional", alias="ODDS_OVERROUND_METHOD"
    )
    value_min_edge_pct: float = Field(default=3.0, alias="VALUE_MIN_EDGE_PCT")
    value_min_confidence: float = Field(default=0.6, alias="VALUE_MIN_CONFIDENCE")
    value_max_picks: int = Field(default=5, alias="VALUE_MAX_PICKS")
    value_markets: tuple[str, ...] = Field(
        default=("1X2", "OU_2_5", "BTTS"), alias="VALUE_MARKETS"
    )
    enable_value_features: bool = Field(default=False, alias="ENABLE_VALUE_FEATURES")

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

    @field_validator("value_markets", mode="before")
    @classmethod
    def _split_value_markets(
        cls, value: tuple[str, ...] | str | None
    ) -> tuple[str, ...]:
        if value is None:
            return ("1X2", "OU_2_5", "BTTS")
        if isinstance(value, tuple):
            return value
        if not value:
            return tuple()
        return tuple(item.strip() for item in value.split(",") if item.strip())

    @property
    def odds(self) -> OddsSettings:
        return OddsSettings(
            provider=self.odds_provider,
            refresh_sec=self.odds_refresh_sec,
            rps_limit=float(self.odds_rps_limit),
            timeout_sec=float(self.odds_timeout_sec),
            retry_attempts=int(self.odds_retry_attempts),
            backoff_base=float(self.odds_backoff_base),
            overround_method=self.odds_overround_method,
        )

    @property
    def value(self) -> ValueSettings:
        return ValueSettings(
            min_edge_pct=float(self.value_min_edge_pct),
            min_confidence=float(self.value_min_confidence),
            max_picks=int(self.value_max_picks),
            markets=self.value_markets,
        )

    @property
    def deployment_env(self) -> str:
        if self.canary:
            return "canary"
        return self.env or "local"

    def model_post_init(self, __context: Any) -> None:
        if not self.sportmonks_api_token:
            for env_name, value in (
                ("SPORTMONKS_TOKEN", getattr(self, "sportmonks_token", "")),
                ("SPORTMONKS_API_KEY", self.sportmonks_api_key),
            ):
                if value:
                    object.__setattr__(self, "sportmonks_api_token", value)
                    logger.warning(
                        "%s is deprecated; use SPORTMONKS_API_TOKEN",
                        env_name,
                    )
                    break

    def _build_pg_dsn(self, host: str | None) -> str:
        host_value = (host or self.pg_host_default or "").strip()
        if not host_value:
            return ""

        user = _q(self.pg_user or "")
        password = _q(self.pg_password or "")
        credentials = ""
        if user or password:
            credentials = user
            if password:
                credentials = f"{credentials}:{password}"
            credentials = f"{credentials}@"

        database = self.pg_database or ""
        return (
            "postgresql+asyncpg://"
            f"{credentials}{host_value}:{int(self.pg_port)}/{database}"
        )

    def get_database_url(self, mode: str = "rw") -> str:
        normalized = (mode or "rw").lower()
        direct_map = {
            "rw": self.database_url_rw,
            "ro": self.database_url_ro,
            "rr": self.database_url_rr,
        }
        direct = direct_map.get(normalized, self.database_url_rw)
        if direct:
            return direct

        host_map = {
            "rw": self.pg_host_rw,
            "ro": self.pg_host_ro,
            "rr": self.pg_host_rr,
        }
        return self._build_pg_dsn(host_map.get(normalized, self.pg_host_rw))

    def get_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url

        password = _q(self.redis_password or "")
        auth = f"default:{password}@"
        host = self.redis_host or "localhost"
        return f"redis://{auth}{host}:{int(self.redis_port)}/{int(self.redis_db)}"


def _q(value: str | None) -> str:
    return _u.quote(value or "", safe="")


def get_database_url(mode: str = "rw") -> str:
    return get_settings().get_database_url(mode)


def get_redis_url() -> str:
    return get_settings().get_redis_url()


@lru_cache(1)
def get_settings() -> Settings:
    return Settings()  # auto-reads env via pydantic-settings v2


def reset_settings_cache() -> None:
    """Сброс кэша настроек для тестов/смоуков при смене env."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
