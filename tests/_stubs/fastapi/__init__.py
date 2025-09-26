"""
/**
 * @file: tests/_stubs/fastapi/__init__.py
 * @description: Minimal FastAPI stub for offline testing
 * @dependencies: types.SimpleNamespace
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

__all__ = [
    "FastAPI",
    "HTTPException",
    "Request",
    "Response",
    "status",
]


class HTTPException(Exception):
    """Minimal HTTPException stub matching FastAPI signature."""

    def __init__(self, status_code: int, detail: Any | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class Response:
    """Lightweight response container used by JSONResponse stub."""

    def __init__(
        self,
        *,
        content: Any = None,
        media_type: str | None = None,
        status_code: int = 200,
    ) -> None:
        self.content = content
        self.media_type = media_type
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        if media_type:
            self.headers["content-type"] = media_type


class FastAPI:
    """Very small subset of FastAPI used in tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple stub
        self.routes: dict[str, Callable[..., Any]] = {}

    def add_middleware(self, *_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
        return

    def mount(self, path: str, app: Any) -> None:  # pragma: no cover
        self.routes[path] = app

    def get(self, path: str, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes[path] = func
            return func

        return decorator

    def middleware(self, _type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # pragma: no cover
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator


class Request:  # pragma: no cover - placeholder for type hints
    pass


status = SimpleNamespace(
    HTTP_200_OK=200,
    HTTP_404_NOT_FOUND=404,
    HTTP_503_SERVICE_UNAVAILABLE=503,
)
