"""
/**
 * @file: aiogram/types/__init__.py
 * @description: Minimal aiogram types for offline command tests.
 * @dependencies: typing
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "CallbackQuery",
    "CommandObject",
    "FSInputFile",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "Message",
    "User",
]


@dataclass(slots=True)
class CommandObject:
    command: str | None = None
    args: str | None = None


@dataclass(slots=True)
class User:
    id: int = 0


@dataclass(slots=True)
class Message:
    text: str | None = None
    from_user: Optional[User] = None

    async def answer(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def reply(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def edit_text(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@dataclass(slots=True)
class FSInputFile:
    path: str
    filename: str | None = None


@dataclass(slots=True)
class CallbackQuery:
    data: str | None = None
    message: Optional[Message] = None

    async def answer(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@dataclass(slots=True)
class InlineKeyboardButton:
    text: str
    callback_data: str | None = None


@dataclass(slots=True)
class InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]]

