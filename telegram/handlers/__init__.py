"""
@file: telegram/handlers/__init__.py
@description: Router registration for Telegram bot with DI support.
@dependencies: aiogram, telegram.dependencies
@created: 2025-09-19
"""
from __future__ import annotations

from aiogram import Dispatcher

from telegram.dependencies import BotDependencies, build_default_dependencies

from . import help as help_handler
from . import match as match_handler
from . import model as model_handler
from . import predict as predict_handler
from . import start, terms
from . import today as today_handler


def register_handlers(dp: Dispatcher, deps: BotDependencies | None = None) -> BotDependencies:
    deps = deps or build_default_dependencies()
    dp.include_router(start.router)
    dp.include_router(help_handler.create_router(deps))
    dp.include_router(model_handler.create_router(deps))
    dp.include_router(today_handler.create_router(deps))
    dp.include_router(match_handler.create_router(deps))
    dp.include_router(predict_handler.create_router(deps))
    dp.include_router(terms.router)
    return deps
