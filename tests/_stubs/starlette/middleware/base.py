"""
/**
 * @file: tests/_stubs/starlette/middleware/base.py
 * @description: Minimal BaseHTTPMiddleware stub for offline tests
 * @dependencies: None
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

from typing import Any

__all__ = ["BaseHTTPMiddleware"]


class BaseHTTPMiddleware:  # pragma: no cover - placeholder
    def __init__(self, app: Any) -> None:
        self.app = app

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        return await call_next(request)
