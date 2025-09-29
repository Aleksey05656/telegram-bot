"""
/**
 * @file: tests/_stubs/alembic/config.py
 * @description: Offline stub for alembic.config.Config class used in tests.
 * @dependencies: none
 * @created: 2025-09-30
 */
"""

from __future__ import annotations


class Config:
    """Minimal stub replicating alembic.config.Config interface used in tests."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        self._options: dict[str, str] = {}

    def set_main_option(self, key: str, value: str) -> None:  # pragma: no cover - trivial
        self._options[key] = value

    def get_main_option(
        self, key: str, default: str | None = None
    ) -> str | None:  # pragma: no cover - helper
        return self._options.get(key, default)


__all__ = ["Config"]
