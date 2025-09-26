"""
/**
 * @file: tests/_stubs/fastapi/testclient.py
 * @description: Minimal TestClient stub for FastAPI offline mode
 * @dependencies: asyncio, tests._stubs.fastapi.Response
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

import asyncio
from typing import Any

from . import HTTPException, Response

__all__ = ["TestClient"]


class _ResultWrapper:
    def __init__(self, response: Response) -> None:
        self._response = response
        self.status_code = getattr(response, "status_code", 200)
        self.headers = getattr(response, "headers", {})

    @property
    def text(self) -> str:
        content = getattr(self._response, "content", "")
        if isinstance(content, (bytes, bytearray)):
            return content.decode("utf-8")
        return str(content)

    def json(self) -> Any:
        return getattr(self._response, "content", None)


class TestClient:
    """Very small synchronous test client for stubbed FastAPI."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def get(self, path: str) -> _ResultWrapper:
        handler = getattr(self.app, "routes", {}).get(path)
        if handler is None:
            return _ResultWrapper(Response(status_code=404, content=None, media_type="application/json"))

        try:
            result = handler()
        except HTTPException as exc:
            return _ResultWrapper(
                Response(
                    status_code=getattr(exc, "status_code", 500),
                    content={"detail": exc.detail} if exc.detail is not None else None,
                    media_type="application/json",
                )
            )

        if asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(result)
                except HTTPException as exc:
                    return _ResultWrapper(
                        Response(
                            status_code=getattr(exc, "status_code", 500),
                            content={"detail": exc.detail} if exc.detail is not None else None,
                            media_type="application/json",
                        )
                    )
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        if not isinstance(result, Response):
            result = Response(content=result)
        return _ResultWrapper(result)
