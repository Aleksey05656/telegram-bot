"""
@file: tgbotapp/dependencies.py
@description: Dependency contracts and builders for Telegram handlers.
@dependencies: dataclasses, typing, config
@created: 2025-09-19
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from config import get_settings
from tgbotapp import services


class PredictionTaskQueue(Protocol):
    """Queue abstraction used by /predict handler."""

    def enqueue(self, chat_id: int, home_team: str, away_team: str) -> str | None:
        """Schedule a prediction job and return job id."""


class FixturesRepository(Protocol):
    """Data access facade for fixtures used by /today and /match."""

    async def list_fixtures_for_date(self, target_date: date) -> list[dict[str, Any]]:
        """Return fixtures scheduled for the given date."""

    async def get_fixture(self, fixture_id: int) -> dict[str, Any] | None:
        """Return fixture metadata by identifier."""


class PredictorService(Protocol):
    """Synchronous prediction interface for /match."""

    async def get_prediction(self, fixture_id: int) -> dict[str, Any]:
        """Return fully formatted prediction payload."""


@dataclass(frozen=True)
class CommandInfo:
    command: str
    description: str


@dataclass(frozen=True)
class ModelMetadata:
    app_version: str
    git_sha: str
    simulations: int
    modifiers: Sequence[str]
    datasource: str
    redis_masked: str


@dataclass(frozen=True)
class BotDependencies:
    command_catalog: Sequence[CommandInfo]
    model_meta: ModelMetadata
    fixtures_repo: FixturesRepository
    predictor: PredictorService
    task_queue: PredictionTaskQueue


def _mask_secret(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" in netloc:
        creds, host = netloc.rsplit("@", 1)
        if ":" in creds:
            creds = "***:***"
        elif creds:
            creds = "***"
        netloc = f"{creds}@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _detect_datasource(dsn: str) -> str:
    if dsn.startswith("sqlite"):
        return "sqlite"
    if dsn.startswith("postgres") or "://" in dsn and "postgres" in dsn:
        return "postgres"
    return "unknown"


def build_default_dependencies() -> BotDependencies:
    settings = get_settings()
    command_catalog = (
        CommandInfo("start", "Начало работы"),
        CommandInfo("help", "Справка и список команд"),
        CommandInfo("model", "Версия и конфигурация модели"),
        CommandInfo("today", "Матчи на сегодня"),
        CommandInfo("match", "Прогноз по идентификатору"),
        CommandInfo("predict", "Поставить задачу в очередь"),
        CommandInfo("terms", "Условия использования"),
    )
    modifiers = [name for name, enabled in settings.MODEL_FLAGS.items() if enabled]
    model_meta = ModelMetadata(
        app_version=settings.APP_VERSION,
        git_sha=settings.GIT_SHA,
        simulations=settings.SIM_N,
        modifiers=tuple(modifiers),
        datasource=_detect_datasource(settings.DATABASE_URL),
        redis_masked=_mask_secret(settings.REDIS_URL),
    )

    fixtures_repo: FixturesRepository = services.SportMonksFixturesRepository()
    predictor: PredictorService = services.DeterministicPredictorService(fixtures_repo)
    task_queue: PredictionTaskQueue = services.TaskManagerQueue()

    return BotDependencies(
        command_catalog=command_catalog,
        model_meta=model_meta,
        fixtures_repo=fixtures_repo,
        predictor=predictor,
        task_queue=task_queue,
    )
