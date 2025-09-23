"""
@file: telegram/handlers/__init__.py
@description: Router registration for Telegram bot with DI support.
@dependencies: aiogram, telegram.dependencies
@created: 2025-09-19
"""
from __future__ import annotations

from aiogram import Dispatcher

from app.bot import build_bot_router
from telegram.dependencies import BotDependencies, build_default_dependencies

from . import terms


def register_handlers(dp: Dispatcher, deps: BotDependencies | None = None) -> BotDependencies:
    deps = deps or build_default_dependencies()
    dp.include_router(build_bot_router())
    dp.include_router(terms.router)
    return deps
