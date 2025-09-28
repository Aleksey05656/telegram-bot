"""
@file: middlewares.py
@description: Basic FastAPI middlewares
@dependencies: fastapi
@created: 2025-09-09
"""

import time
from collections.abc import Callable

from .fastapi_compat import BaseHTTPMiddleware, Request


class ProcessingTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.perf_counter() - start)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests: int, per_seconds: int):
        super().__init__(app)
        self.requests = requests
        self.per_seconds = per_seconds

    async def dispatch(self, request: Request, call_next: Callable):
        return await call_next(request)
