"""
/**
 * @file: aiogram/filters/__init__.py
 * @description: Minimal command filter placeholder.
 * @dependencies: none
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from aiogram.types import CommandObject as _CommandObject

__all__ = ["Command", "CommandObject"]


class Command:
    """Stub storing command names without any logic."""

    def __init__(self, *_commands: str) -> None:
        self.commands = tuple(_commands)


CommandObject = _CommandObject

