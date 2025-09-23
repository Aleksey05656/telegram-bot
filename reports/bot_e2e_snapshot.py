"""
@file: bot_e2e_snapshot.py
@description: Generate deterministic Markdown snapshot of key bot commands for CI artifacts.
@dependencies: config, telegram.handlers
@created: 2025-09-22
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("LOG_LEVEL", "WARNING")

from config import get_settings  # noqa: E402
from database.db_router import mask_dsn  # noqa: E402
from telegram.dependencies import BotDependencies, CommandInfo, ModelMetadata  # noqa: E402
from telegram.handlers import help as help_handler  # noqa: E402
from telegram.handlers import match as match_handler  # noqa: E402
from telegram.handlers import model as model_handler  # noqa: E402
from telegram.handlers import predict as predict_handler  # noqa: E402
from telegram.handlers import today as today_handler  # noqa: E402

SNAPSHOT_SEED = 20240922
_DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data"))
_REPORTS_ROOT = Path(os.getenv("REPORTS_DIR", str(_DATA_ROOT / "reports")))
SNAPSHOT_PATH = _REPORTS_ROOT / "bot_e2e_snapshot.md"


class SnapshotQueue:
    def __init__(self, job_id: str = "snap-queue-001") -> None:
        self.job_id = job_id
        self.enqueued: list[tuple[int, str, str]] = []

    def enqueue(self, chat_id: int, home_team: str, away_team: str) -> str:
        self.enqueued.append((chat_id, home_team, away_team))
        return self.job_id


class SnapshotFixturesRepo:
    async def list_fixtures_for_date(self, target_date):
        kickoff = datetime(2025, 1, 2, 18, 45, tzinfo=datetime.UTC)
        return [
            {
                "id": 77,
                "home": "Alpha <FC>",
                "away": "Beta & Co",
                "league": "Premier",
                "kickoff": kickoff,
            },
            {
                "id": 88,
                "home": "Gamma",
                "away": "Delta",
                "league": "Championship",
                "kickoff": kickoff.replace(hour=21, minute=0),
            },
        ]

    async def get_fixture(self, fixture_id: int) -> dict[str, Any]:
        base = {
            "home": "Alpha",
            "away": "Beta",
            "league": "Premier",
            "kickoff": datetime(2025, 1, 2, 18, 45, tzinfo=datetime.UTC),
        }
        return {"id": fixture_id, **base}


class SnapshotPredictor:
    async def get_prediction(self, fixture_id: int) -> dict[str, Any]:
        random.seed(SNAPSHOT_SEED + fixture_id)
        return {
            "fixture": {
                "id": fixture_id,
                "home": "Alpha",
                "away": "Beta",
                "league": "Premier",
                "kickoff": datetime(2025, 1, 2, 18, 45, tzinfo=datetime.UTC),
            },
            "markets": {
                "1x2": {"home": 0.47, "draw": 0.26, "away": 0.27},
            },
            "totals": {
                "2.5": {"over": 0.58, "under": 0.42},
                "3.5": {"over": 0.31, "under": 0.69},
            },
            "both_teams_to_score": {"yes": 0.53, "no": 0.47},
            "top_scores": [
                ("2:1", 0.13),
                ("1:1", 0.11),
                ("0:1", 0.08),
            ],
        }


def _detect_datasource(dsn: str) -> str:
    lowered = dsn.lower()
    if lowered.startswith("sqlite"):
        return "sqlite"
    if "postgres" in lowered:
        return "postgres"
    return "unknown"


def build_dependencies() -> tuple[BotDependencies, dict[str, str]]:
    settings = get_settings()
    modifiers = tuple(sorted(name for name, enabled in settings.MODEL_FLAGS.items() if enabled))
    redis_masked = mask_dsn(settings.REDIS_URL)
    metadata = ModelMetadata(
        app_version=settings.APP_VERSION,
        git_sha=settings.GIT_SHA,
        simulations=settings.SIM_N,
        modifiers=modifiers,
        datasource=_detect_datasource(settings.DATABASE_URL),
        redis_masked=redis_masked,
    )
    command_catalog = (
        CommandInfo("start", "Начало работы"),
        CommandInfo("help", "Справка"),
        CommandInfo("model", "Версия модели"),
        CommandInfo("today", "Матчи"),
        CommandInfo("match", "Прогноз"),
        CommandInfo("predict", "Очередь"),
    )
    deps = BotDependencies(
        command_catalog=command_catalog,
        model_meta=metadata,
        fixtures_repo=SnapshotFixturesRepo(),
        predictor=SnapshotPredictor(),
        task_queue=SnapshotQueue(),
    )
    meta = {
        "app_version": settings.APP_VERSION,
        "git_sha": settings.GIT_SHA,
        "redis_masked": redis_masked,
    }
    return deps, meta


async def collect_responses(deps: BotDependencies) -> dict[str, str]:
    snapshot_now = datetime(2025, 1, 1, 19, 0, tzinfo=datetime.UTC)
    help_text = help_handler.build_help_text(tuple(deps.command_catalog))
    model_text = model_handler.render_model_info(deps.model_meta)
    today_text = await today_handler.build_today_response(deps, now=snapshot_now)
    match_text = await match_handler.build_match_response(deps, 77)
    predict_text = await predict_handler.build_predict_response(
        deps,
        chat_id=4242,
        query="Alpha <FC> — Beta & Co",
    )
    return {
        "help": help_text,
        "model": model_text,
        "today": today_text,
        "match": match_text,
        "predict": predict_text,
    }


def render_snapshot(metadata: dict[str, str], responses: dict[str, str], generated_at: datetime) -> str:
    lines = [
        "# Bot E2E Snapshot",
        "",
        f"- Generated at: {generated_at.isoformat()}",
        f"- Seed: {SNAPSHOT_SEED}",
        f"- APP_VERSION: {metadata['app_version']}",
        f"- GIT_SHA: {metadata['git_sha']}",
    ]
    if metadata.get("redis_masked"):
        lines.append(f"- Redis (masked): {metadata['redis_masked']}")

    sections = []
    for command in ("help", "model", "today", "match", "predict"):
        sections.append(
            f"## /{command}\n\n```html\n{responses[command]}\n```"
        )

    return "\n".join(lines + ["", *sections]) + "\n"


def main() -> None:
    random.seed(SNAPSHOT_SEED)
    deps, metadata = build_dependencies()
    generated_at = datetime.now(datetime.UTC)
    responses = asyncio.run(collect_responses(deps))
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        render_snapshot(metadata, responses, generated_at),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

