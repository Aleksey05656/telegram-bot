"""
/**
 * @file: app/bot/__init__.py
 * @description: Utilities for assembling Telegram bot routers and dependencies.
 * @dependencies: aiogram, app.bot.routers.commands, app.bot.routers.callbacks
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from aiogram import Router

from .routers.callbacks import callbacks_router
from .routers.commands import commands_router


def build_bot_router() -> Router:
    """Return the root router that wires command and callback routers."""

    root = Router()
    root.include_router(commands_router)
    root.include_router(callbacks_router)
    return root


__all__ = ["build_bot_router", "commands_router", "callbacks_router"]
