"""
@file: tgbotapp/handlers/help.py
@description: Handler for /help command with dependency-aware routing.
@dependencies: aiogram, tgbotapp.dependencies
@created: 2025-09-19
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from tgbotapp.dependencies import BotDependencies, CommandInfo


def build_help_text(commands: tuple[CommandInfo, ...] | list[CommandInfo]) -> str:
    lines = ["ℹ️ <b>Команды бота</b>"]
    for info in commands:
        lines.append(f"• /{info.command} — {info.description}")
    return "\n".join(lines)


def create_router(deps: BotDependencies) -> Router:
    router = Router()

    help_text = build_help_text(tuple(deps.command_catalog))

    @router.message(Command("help"))
    async def handle_help(message: Message) -> None:  # pragma: no cover - executed in runtime
        await message.answer(help_text, parse_mode="HTML")

    return router
