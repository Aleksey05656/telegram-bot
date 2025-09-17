"""
@file: tests/bot/test_handlers_smoke.py
@description: Smoke tests for Telegram handlers.
@dependencies: telegram.handlers, telegram.widgets
@created: 2025-09-19
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from telegram.dependencies import BotDependencies, CommandInfo, ModelMetadata
from telegram.handlers import help as help_handler
from telegram.handlers import match as match_handler
from telegram.handlers import model as model_handler
from telegram.handlers import predict as predict_handler
from telegram.handlers import today as today_handler


class DummyQueue:
    def __init__(self, job_id: str = "job-123") -> None:
        self.job_id = job_id
        self.calls: list[tuple[int, str, str]] = []

    def enqueue(self, chat_id: int, home_team: str, away_team: str) -> str:
        self.calls.append((chat_id, home_team, away_team))
        return self.job_id


class DummyFixturesRepo:
    async def list_fixtures_for_date(self, target_date):  # pragma: no cover - simple mock
        return [
            {
                "id": 77,
                "home": "Alpha <FC>",
                "away": "Beta & Co",
                "league": "Premier",
                "kickoff": datetime(2025, 1, 1, 18, 30, tzinfo=timezone.utc),
            }
        ]

    async def get_fixture(self, fixture_id: int):  # pragma: no cover - simple mock
        return {
            "id": fixture_id,
            "home": "Alpha",
            "away": "Beta",
            "league": "Premier",
            "kickoff": datetime(2025, 1, 1, 18, 30, tzinfo=timezone.utc),
        }


class DummyPredictor:
    async def get_prediction(self, fixture_id: int):  # pragma: no cover - simple mock
        return {
            "fixture": {
                "id": fixture_id,
                "home": "Alpha",
                "away": "Beta",
                "league": "Premier",
                "kickoff": datetime(2025, 1, 1, 18, 30, tzinfo=timezone.utc),
            },
            "markets": {"1x2": {"home": 0.45, "draw": 0.25, "away": 0.30}},
            "totals": {"2.5": {"over": 0.55, "under": 0.45}},
            "both_teams_to_score": {"yes": 0.52, "no": 0.48},
            "top_scores": [("2:1", 0.12), ("1:1", 0.11), ("0:1", 0.08)],
        }


@pytest.fixture
def deps() -> BotDependencies:
    command_catalog = (
        CommandInfo("start", "Начало"),
        CommandInfo("help", "Справка"),
        CommandInfo("model", "Версия"),
        CommandInfo("today", "Матчи"),
        CommandInfo("match", "Прогноз"),
        CommandInfo("predict", "Очередь"),
        CommandInfo("terms", "Условия"),
    )
    meta = ModelMetadata(
        app_version="1.2.3",
        git_sha="abcdef",
        simulations=10000,
        modifiers=("weather", "form"),
        datasource="postgres",
        redis_masked="redis://***:***@host:6379/0",
    )
    return BotDependencies(
        command_catalog=command_catalog,
        model_meta=meta,
        fixtures_repo=DummyFixturesRepo(),
        predictor=DummyPredictor(),
        task_queue=DummyQueue(),
    )


pytestmark = pytest.mark.bot_smoke


def test_help_lists_all_commands(deps: BotDependencies) -> None:
    text = help_handler.build_help_text(tuple(deps.command_catalog))
    for info in deps.command_catalog:
        assert f"/{info.command}" in text


def test_model_contains_version(deps: BotDependencies) -> None:
    text = model_handler.render_model_info(deps.model_meta)
    assert deps.model_meta.app_version in text
    assert deps.model_meta.git_sha in text


@pytest.mark.asyncio
async def test_predict_returns_job_id(deps: BotDependencies) -> None:
    response = await predict_handler.build_predict_response(deps, chat_id=10, query="Alpha - Beta")
    assert "job-123" in response
    queue = deps.task_queue  # type: ignore[assignment]
    assert isinstance(queue, DummyQueue)
    assert queue.calls == [(10, "Alpha", "Beta")]


@pytest.mark.asyncio
async def test_today_returns_fixtures(deps: BotDependencies) -> None:
    now = datetime(2025, 1, 1, 19, 0, tzinfo=timezone.utc)
    text = await today_handler.build_today_response(deps, now=now)
    assert "77" in text
    assert "Alpha &lt;FC&gt;" in text


@pytest.mark.asyncio
async def test_match_returns_formatted_prediction(deps: BotDependencies) -> None:
    text = await match_handler.build_match_response(deps, 77)
    assert "1X2" in text
    assert "Тоталы" in text
