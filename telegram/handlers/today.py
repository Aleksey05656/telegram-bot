"""
@file: telegram/handlers/today.py
@description: Handler for /today command returning fixture list.
@dependencies: aiogram, telegram.dependencies, telegram.widgets
@created: 2025-09-19
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from logger import logger
from telegram.dependencies import BotDependencies
from telegram.widgets import format_fixture_list


async def build_today_response(deps: BotDependencies, now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    cutoff = current.replace(hour=20, minute=0, second=0, microsecond=0)
    target_date = (current + timedelta(days=1)).date() if current >= cutoff else current.date()
    fixtures = await deps.fixtures_repo.list_fixtures_for_date(target_date)
    if not fixtures:
        return "📭 На выбранную дату матчей нет."
    return format_fixture_list(fixtures)


def create_router(deps: BotDependencies) -> Router:
    router = Router()

    @router.message(Command("today"))
    async def handle_today(message: Message) -> None:  # pragma: no cover - executed in runtime
        try:
            text = await build_today_response(deps)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Не удалось получить список матчей: %s", exc)
            text = "❌ Не удалось получить список матчей."
        await message.answer(text, parse_mode="HTML")

    return router
