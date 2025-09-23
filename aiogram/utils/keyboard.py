"""
/**
 * @file: aiogram/utils/keyboard.py
 * @description: Minimal InlineKeyboardBuilder stub for offline tests.
 * @dependencies: aiogram.types
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

__all__ = ["InlineKeyboardBuilder"]


class InlineKeyboardBuilder:
    """Simplified builder collecting inline keyboard buttons."""

    def __init__(self) -> None:
        self.buttons: List[InlineKeyboardButton] = []
        self._rows: List[List[InlineKeyboardButton]] = []

    def button(self, *, text: str, callback_data: str | None = None) -> InlineKeyboardButton:
        btn = InlineKeyboardButton(text=text, callback_data=callback_data)
        self.buttons.append(btn)
        return btn

    def row(self, *buttons: InlineKeyboardButton) -> None:
        self._rows.append(list(buttons))

    def adjust(self, *sizes: int) -> None:
        if not self.buttons:
            return
        iterator = iter(self.buttons)
        rows: List[List[InlineKeyboardButton]] = []
        for size in sizes:
            row: List[InlineKeyboardButton] = []
            for _ in range(max(1, size)):
                try:
                    row.append(next(iterator))
                except StopIteration:
                    break
            if row:
                rows.append(row)
        remaining = list(iterator)
        for button in remaining:
            rows.append([button])
        self._rows = rows

    def as_markup(self) -> InlineKeyboardMarkup:
        if not self._rows:
            self._rows = [[button] for button in self.buttons]
        return InlineKeyboardMarkup(inline_keyboard=self._rows)

