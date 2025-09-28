"""
/**
 * @file: app/bot/__init__.py
 * @description: Utilities for assembling Telegram bot routers and dependencies.
 * @dependencies: aiogram, app.bot.routers.commands, app.bot.routers.callbacks
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

try:  # pragma: no cover - optional dependency guard
    from aiogram import Router
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    class Router:  # type: ignore[override]
        def include_router(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
            return None


def _load_router(name: str) -> Any | None:
    try:
        module = import_module(f".routers.{name}", __name__)
    except ModuleNotFoundError:  # pragma: no cover - offline fallback
        return None
    return getattr(module, f"{name}_router", None)


def build_bot_router() -> Router:
    """Return the root router that wires command and callback routers."""

    root = Router()
    for name in ("commands", "callbacks"):
        router = _load_router(name)
        if router is not None:
            root.include_router(router)
    return root


__all__ = ["build_bot_router"]
