/**
 * @file: telegram/middlewares.py
 * @description: Custom middlewares for Telegram bot.
 * @dependencies: aiogram
 * @created: 2025-08-24
 */
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RateLimitMiddleware(BaseMiddleware):
    """Simple per-user rate limiting."""

    def __init__(self, limit: float = 1.0) -> None:
        self.limit = limit
        self._last_call: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None:
            now = time.monotonic()
            last = self._last_call.get(user.id, 0.0)
            if now - last < self.limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("Слишком много запросов. Попробуйте позже.", show_alert=True)
                else:
                    await event.answer("Слишком много запросов. Попробуйте позже.")
                return
            self._last_call[user.id] = now
        return await handler(event, data)
