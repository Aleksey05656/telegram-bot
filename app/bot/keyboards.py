"""
/**
 * @file: app/bot/keyboards.py
 * @description: Inline keyboard factories for pagination, match details and exports.
 * @dependencies: aiogram
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def today_keyboard(
    matches: Iterable[dict[str, object]],
    *,
    query_hash: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for match in matches:
        match_id = match.get("id")
        if match_id is None:
            continue
        title = f"Подробнее · {match.get('home')} vs {match.get('away')}"
        builder.button(
            text=title,
            callback_data=f"match:{match_id}:{query_hash}:{page}",
        )
    if builder.buttons:
        builder.adjust(1)
    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"page:{query_hash}:{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"page:{query_hash}:{page+1}"))
    builder.row(*nav_row)
    return builder.as_markup()


def match_details_keyboard(
    match_id: int,
    *,
    query_hash: str | None = None,
    page: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧠 Объяснить", callback_data=f"explain:{match_id}")
    builder.button(text="📤 Экспорт", callback_data=f"export:{match_id}")
    if query_hash:
        back_payload = f"back:{query_hash}:{page or 1}"
        builder.button(text="⬅️ Назад", callback_data=back_payload)
        builder.adjust(2, 1)
    else:
        builder.adjust(2)
    return builder.as_markup()


def noop_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="OK", callback_data="noop")
    builder.adjust(1)
    return builder.as_markup()


__all__ = ["today_keyboard", "match_details_keyboard", "noop_keyboard"]
