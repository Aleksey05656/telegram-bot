"""
@file: tests/bot/test_handlers_errors.py
@description: Edge-case coverage for tgbotapp bot command handlers.
@dependencies: tgbotapp.handlers.predict, tgbotapp.handlers.match, tgbotapp.handlers.today
@created: 2025-09-23
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tgbotapp.dependencies import BotDependencies, ModelMetadata
from tgbotapp.handlers.match import build_match_response, create_router
from tgbotapp.handlers.predict import (
    _MISSING_TEAMS_MESSAGE,
    _QUEUE_ERROR_MESSAGE,
    _USAGE_MESSAGE,
    build_predict_response,
)
from tgbotapp.handlers.today import build_today_response
from tgbotapp.services import MatchNotFoundError


class DummyQueue:
    def __init__(self, *, job_id: str | None = "job-1", returns_coroutine: bool = False):
        self.job_id = job_id
        self.returns_coroutine = returns_coroutine
        self.calls: list[tuple[int, str, str]] = []

    def enqueue(self, chat_id: int, home: str, away: str):
        self.calls.append((chat_id, home, away))
        if self.job_id is None:
            return None

        async def _coro() -> str:
            return self.job_id

        return _coro() if self.returns_coroutine else self.job_id


class DummyFixturesRepo:
    def __init__(self, *, fixtures: dict[int, dict[str, str]] | None = None, today: list[dict[str, str]] | None = None):
        self._fixtures = fixtures or {}
        self._today = today or []
        self.list_calls: list = []

    async def list_fixtures_for_date(self, target_date):  # type: ignore[override]
        self.list_calls.append(target_date)
        return list(self._today)

    async def get_fixture(self, fixture_id: int):  # type: ignore[override]
        return self._fixtures.get(int(fixture_id))


class DummyPredictor:
    def __init__(self, *, payloads: dict[int, dict] | None = None, missing: set[int] | None = None):
        self._payloads = payloads or {}
        self._missing = missing or set()
        self.calls: list[int] = []

    async def get_prediction(self, fixture_id: int):  # type: ignore[override]
        self.calls.append(int(fixture_id))
        if int(fixture_id) in self._missing:
            raise MatchNotFoundError(f"Fixture {fixture_id} not found")
        return self._payloads.get(int(fixture_id), {"fixture": {"home": "A", "away": "B"}, "markets": {"1x2": {}}})


@pytest.fixture
def bot_meta() -> ModelMetadata:
    return ModelMetadata(
        app_version="v-test",
        git_sha="sha-test",
        simulations=10,
        modifiers=(),
        datasource="sqlite",
        redis_masked="redis://***@localhost/0",
    )


def make_deps(
    *,
    queue: DummyQueue | None = None,
    fixtures: DummyFixturesRepo | None = None,
    predictor: DummyPredictor | None = None,
    meta: ModelMetadata | None = None,
) -> BotDependencies:
    model_meta = meta or ModelMetadata(
        app_version="v-default",
        git_sha="sha-default",
        simulations=0,
        modifiers=(),
        datasource="sqlite",
        redis_masked="redis://***@localhost/0",
    )
    return BotDependencies(
        command_catalog=(),
        model_meta=model_meta,
        fixtures_repo=fixtures or DummyFixturesRepo(),
        predictor=predictor or DummyPredictor(),
        task_queue=queue or DummyQueue(),
    )


@pytest.mark.asyncio
async def test_predict_empty_input_returns_usage(bot_meta: ModelMetadata) -> None:
    deps = make_deps(meta=bot_meta)
    result = await build_predict_response(deps, chat_id=1, query="")
    assert result == _USAGE_MESSAGE


@pytest.mark.asyncio
async def test_predict_single_team_without_separator(bot_meta: ModelMetadata) -> None:
    deps = make_deps(meta=bot_meta)
    result = await build_predict_response(deps, chat_id=1, query="Зенит")
    assert result == _MISSING_TEAMS_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", ["-", "—", "–"])
async def test_predict_accepts_various_dashes(separator: str, bot_meta: ModelMetadata) -> None:
    queue = DummyQueue(job_id="pred-42", returns_coroutine=True)
    deps = make_deps(queue=queue, meta=bot_meta)
    query = f"Спартак {separator} Зенит"
    result = await build_predict_response(deps, chat_id=123, query=query)
    assert "pred-42" in result
    assert "Спартак" in result
    assert "Зенит" in result
    assert queue.calls == [(123, "Спартак", "Зенит")]


@pytest.mark.asyncio
async def test_predict_html_escape_and_no_traceback(bot_meta: ModelMetadata) -> None:
    queue = DummyQueue(job_id="<job>")
    deps = make_deps(queue=queue, meta=bot_meta)
    result = await build_predict_response(deps, chat_id=5, query="<b>Team</b> - <i>Другой</i>")
    assert "&lt;b&gt;Team&lt;/b&gt;" in result
    assert "&lt;i&gt;Другой&lt;/i&gt;" in result
    assert "Traceback" not in result
    assert "&lt;job&gt;" in result


@pytest.mark.asyncio
async def test_predict_returns_queue_error_on_failure(bot_meta: ModelMetadata) -> None:
    queue = DummyQueue(job_id=None)
    deps = make_deps(queue=queue, meta=bot_meta)
    result = await build_predict_response(deps, chat_id=1, query="A - B")
    assert result == _QUEUE_ERROR_MESSAGE


@pytest.mark.asyncio
async def test_match_handler_reports_not_found(bot_meta: ModelMetadata) -> None:
    predictor = DummyPredictor(missing={99})
    deps = make_deps(predictor=predictor, meta=bot_meta)
    router = create_router(deps)
    handler = router.message.handlers[0].callback

    message = SimpleNamespace(
        text="/match 99",
        chat=SimpleNamespace(id=55),
        replies=[],
    )

    async def _answer(text: str, *, parse_mode: str | None = None) -> None:
        message.replies.append((text, parse_mode))

    message.answer = _answer  # type: ignore[attr-defined]

    await handler(message)
    assert message.replies[0][0] == "Матч не найден"


@pytest.mark.asyncio
async def test_match_response_passes_fixture_to_predictor(bot_meta: ModelMetadata) -> None:
    predictor = DummyPredictor(payloads={7: {"fixture": {"home": "A", "away": "B"}, "markets": {"1x2": {}}}})
    deps = make_deps(predictor=predictor, meta=bot_meta)
    result = await build_match_response(deps, 7)
    assert predictor.calls == [7]
    assert "A — B" in result


@pytest.mark.asyncio
async def test_today_empty_schedule_message(bot_meta: ModelMetadata) -> None:
    fixtures = DummyFixturesRepo(today=[])
    deps = make_deps(fixtures=fixtures, meta=bot_meta)
    message = await build_today_response(deps)
    assert message == "📭 На выбранную дату матчей нет."
    assert fixtures.list_calls, "fixtures repository should be queried"

