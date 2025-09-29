"""
@file: api/__init__.py
@description: Public exports for lightweight API routers.
@dependencies: api.health
@created: 2025-11-07
"""

from __future__ import annotations

from .health import router as health_router

__all__ = ["health_router"]
