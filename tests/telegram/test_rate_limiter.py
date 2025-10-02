"""
/**
 * @file: tests/telegram/test_rate_limiter.py
 * @description: Tests for AsyncRateLimiter behaviour and safe message sending wrapper.
 * @dependencies: asyncio, pytest, tgbotapp.sender
 * @created: 2025-10-02
 */
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tgbotapp.ratelimiter import AsyncRateLimiter
from tgbotapp.sender import get_rate_limiter, safe_send_text, set_rate_limiter


class _StubLimiter:
    def __init__(self) -> None:
        self.calls: list[int | str] = []

    async def acquire(self, chat_id: int | str) -> None:
        self.calls.append(chat_id)


class _StubBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int | str, str, dict[str, Any]]] = []

    async def send_message(
        self, *, chat_id: int | str, text: str, **kwargs: Any
    ) -> dict[str, Any]:
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        self.calls.append((chat_id, text, kwargs))
        return payload


@pytest.mark.asyncio
async def test_safe_send_text_invokes_limiter_and_bot_call() -> None:
    bot = _StubBot()
    limiter = _StubLimiter()
    original = get_rate_limiter()
    set_rate_limiter(limiter)
    try:
        result = await safe_send_text(bot, 123, "hello", parse_mode="HTML")
    finally:
        set_rate_limiter(original)
    assert limiter.calls == [123]
    assert bot.calls == [(123, "hello", {"parse_mode": "HTML"})]
    assert result["text"] == "hello"


@pytest.mark.asyncio
async def test_per_chat_limit_spacing() -> None:
    limiter = AsyncRateLimiter(
        global_limit=10,
        global_window=0.01,
        per_chat_limit=1,
        per_chat_window=0.05,
        group_limit=10,
        group_window=0.05,
    )
    loop = asyncio.get_running_loop()
    await limiter.acquire(42)
    before = loop.time()
    await limiter.acquire(42)
    after = loop.time()
    assert after - before >= 0.045


@pytest.mark.asyncio
async def test_global_limit_across_chats() -> None:
    limiter = AsyncRateLimiter(
        global_limit=2,
        global_window=0.05,
        per_chat_limit=5,
        per_chat_window=0.01,
        group_limit=10,
        group_window=0.05,
    )
    loop = asyncio.get_running_loop()
    await limiter.acquire(1)
    await limiter.acquire(2)
    before = loop.time()
    await limiter.acquire(3)
    after = loop.time()
    assert after - before >= 0.045


@pytest.mark.asyncio
async def test_group_limit_stricter_than_per_chat() -> None:
    limiter = AsyncRateLimiter(
        global_limit=10,
        global_window=0.01,
        per_chat_limit=5,
        per_chat_window=0.01,
        group_limit=2,
        group_window=0.05,
    )
    loop = asyncio.get_running_loop()
    chat_id = -100123
    await limiter.acquire(chat_id)
    await limiter.acquire(chat_id)
    before = loop.time()
    await limiter.acquire(chat_id)
    after = loop.time()
    assert after - before >= 0.045
