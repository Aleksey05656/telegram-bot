"""
@file: tgbotapp/handlers/model.py
@description: Handler for /model command reporting runtime configuration.
@dependencies: aiogram, tgbotapp.dependencies
@created: 2025-09-19
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from tgbotapp.dependencies import BotDependencies, ModelMetadata
from tgbotapp.sender import safe_send_text


def render_model_info(meta: ModelMetadata) -> str:
    modifiers = ", ".join(meta.modifiers) if meta.modifiers else "нет активных модификаторов"
    return "\n".join(
        [
            "🧠 <b>Версия модели</b>",
            f"APP_VERSION: <code>{meta.app_version}</code>",
            f"GIT_SHA: <code>{meta.git_sha}</code>",
            f"Симуляций Монте-Карло: {meta.simulations}",
            f"Модификаторы: {modifiers}",
            f"Источник данных: {meta.datasource}",
            f"Redis: {meta.redis_masked}",
        ]
    )


def create_router(deps: BotDependencies) -> Router:
    router = Router()
    model_text = render_model_info(deps.model_meta)

    @router.message(Command("model"))
    async def handle_model(message: Message) -> None:  # pragma: no cover - executed in runtime
        await safe_send_text(message.bot, message.chat.id, model_text, parse_mode="HTML")

    return router
