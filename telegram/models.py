"""
@file: telegram/models.py
@description: Pydantic models for Telegram command arguments.
@dependencies: pydantic
@created: 2025-08-24
"""
import re

from pydantic import BaseModel, Field


class CommandWithoutArgs(BaseModel):
    """Model for commands that do not accept arguments."""

    @classmethod
    def parse(cls, text: str) -> "CommandWithoutArgs":
        parts = text.strip().split(maxsplit=1)
        if len(parts) > 1:
            raise ValueError("Команда не принимает аргументы")
        return cls()


class PredictCommand(BaseModel):
    """Arguments for the /predict command."""

    home_team: str = Field(..., min_length=1)
    away_team: str = Field(..., min_length=1)

    @classmethod
    def parse(cls, text: str) -> "PredictCommand":
        pattern = re.compile(r"\s*[-—–]\s*")
        parts = [p.strip() for p in pattern.split(text.strip(), maxsplit=1)]
        if len(parts) != 2 or not all(parts):
            raise ValueError("Неверный формат. Используйте: Команда 1 - Команда 2")
        return cls(home_team=parts[0], away_team=parts[1])
