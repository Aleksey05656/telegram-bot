"""
/**
 * @file: tgbotapp/sender.py
 * @description: Safe message sender that applies the AsyncRateLimiter before Telegram calls.
 * @dependencies: aiogram, tgbotapp.ratelimiter
 * @created: 2025-10-02
 */
"""
from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.types import Message

from .ratelimiter import AsyncRateLimiter

_LIMITER = AsyncRateLimiter()


async def safe_send_text(bot: Bot, chat_id: int | str, text: str, **kwargs: Any) -> Message:
    """Send a text message respecting global and per-chat limits."""

    await _LIMITER.acquire(chat_id)
    return await bot.send_message(chat_id=chat_id, text=text, **kwargs)


def get_rate_limiter() -> AsyncRateLimiter:
    """Return the process-wide rate limiter instance."""

    return _LIMITER


def set_rate_limiter(limiter: AsyncRateLimiter) -> None:
    """Override the global rate limiter instance (primarily for testing)."""

    global _LIMITER
    _LIMITER = limiter


__all__ = ["safe_send_text", "get_rate_limiter", "set_rate_limiter", "AsyncRateLimiter"]
