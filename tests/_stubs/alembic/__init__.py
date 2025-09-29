"""
/**
 * @file: tests/_stubs/alembic/__init__.py
 * @description: Package stub exposing alembic.command and alembic.config stubs.
 * @dependencies: tests._stubs.alembic.command, tests._stubs.alembic.config
 * @created: 2025-09-30
 */
"""

from __future__ import annotations

from . import command  # noqa: F401
from .config import Config  # noqa: F401

__all__ = ["command", "Config"]
