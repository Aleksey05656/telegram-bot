"""
@file: telegram/handlers/predict.py
@description: Handler for /predict command using DI queue adapter.
@dependencies: aiogram, telegram.dependencies
@created: 2025-09-19
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from logger import logger
from telegram.dependencies import BotDependencies

_USAGE_MESSAGE = "Укажите команды в формате «Команда 1 — Команда 2»."
_MISSING_TEAMS_MESSAGE = "Нужно указать обе команды."
_QUEUE_ERROR_MESSAGE = "❌ Не удалось поставить задачу. Попробуйте позже."
_SUCCESS_TEMPLATE = (
    "⚙️ Задача поставлена. ID: <code>{job_id}</code>\n" "Матч: {home} — {away}"
)

_PATTERN = re.compile(r"\s*[-—–]\s*")


def parse_matchup(raw: str) -> tuple[str, str]:
    parts = _PATTERN.split(raw.strip(), maxsplit=1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError(_MISSING_TEAMS_MESSAGE)
    home, away = (part.strip() for part in parts)
    return home, away


async def _maybe_await(result: str | None | Awaitable[str | None]) -> str | None:
    if asyncio.iscoroutine(result) or isinstance(result, Awaitable):  # type: ignore[arg-type]
        return await result  # type: ignore[func-returns-value]
    return result


async def build_predict_response(
    deps: BotDependencies, chat_id: int, query: str | None
) -> str:
    if not query:
        return _USAGE_MESSAGE
    try:
        home, away = parse_matchup(query)
    except ValueError as exc:
        return str(exc)

    job_id = await _maybe_await(deps.task_queue.enqueue(chat_id, home, away))
    if not job_id:
        return _QUEUE_ERROR_MESSAGE
    return _SUCCESS_TEMPLATE.format(job_id=escape(str(job_id)), home=escape(home), away=escape(away))


def create_router(deps: BotDependencies) -> Router:
    router = Router()

    @router.message(Command("predict"))
    async def handle_predict(message: Message) -> None:  # pragma: no cover - executed in runtime
        args = message.text.split(maxsplit=1)
        query = args[1] if len(args) > 1 else ""
        response = await build_predict_response(deps, message.chat.id, query)
        await message.answer(response, parse_mode="HTML")
        logger.debug("Predict command processed for chat %s", message.chat.id)

    return router
