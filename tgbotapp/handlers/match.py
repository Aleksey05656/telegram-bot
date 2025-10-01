"""
@file: tgbotapp/handlers/match.py
@description: Handler for /match command performing synchronous prediction.
@dependencies: aiogram, tgbotapp.dependencies, tgbotapp.widgets, tgbotapp.services
@created: 2025-09-19
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from logger import logger
from tgbotapp.dependencies import BotDependencies
from tgbotapp.services import MatchNotFoundError
from tgbotapp.widgets import format_prediction


async def build_match_response(deps: BotDependencies, fixture_id: int) -> str:
    payload = await deps.predictor.get_prediction(fixture_id)
    return format_prediction(payload)


def create_router(deps: BotDependencies) -> Router:
    router = Router()

    @router.message(Command("match"))
    async def handle_match(message: Message) -> None:  # pragma: no cover - executed in runtime
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Неверный id")
            return
        try:
            fixture_id = int(args[1])
        except ValueError:
            await message.answer("Неверный id")
            return
        try:
            text = await build_match_response(deps, fixture_id)
        except MatchNotFoundError:
            await message.answer("Матч не найден")
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Ошибка при получении прогноза для %s: %s", fixture_id, exc)
            await message.answer("❌ Не удалось получить прогноз. Попробуйте позже.")
            return
        await message.answer(text, parse_mode="HTML")

    return router
