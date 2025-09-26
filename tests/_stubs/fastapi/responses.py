"""
/**
 * @file: tests/_stubs/fastapi/responses.py
 * @description: JSONResponse stub compatible with offline FastAPI
 * @dependencies: tests._stubs.fastapi.Response
 * @created: 2025-10-28
 */
"""

from __future__ import annotations

from . import Response

__all__ = ["JSONResponse", "PlainTextResponse"]


class JSONResponse(Response):
    """Very small JSONResponse replacement."""

    def __init__(self, content=None, status_code: int = 200):
        super().__init__(content=content, status_code=status_code, media_type="application/json")


class PlainTextResponse(Response):
    """Minimal plain text response stub."""

    def __init__(self, content: str = "", status_code: int = 200):
        super().__init__(content=content, status_code=status_code, media_type="text/plain")
