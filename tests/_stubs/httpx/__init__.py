"""
/**
 * @file: httpx/__init__.py
 * @description: Simplified asynchronous HTTPX client stubs for offline tests.
 * @dependencies: asyncio, json, urllib.parse
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional
from urllib.parse import urlencode

__all__ = [
    "AsyncBaseTransport",
    "AsyncClient",
    "MockTransport",
    "Request",
    "Response",
    "Timeout",
    "TimeoutException",
    "HTTPStatusError",
]


class Timeout:
    """Placeholder timeout container."""

    def __init__(self, timeout: float) -> None:
        self.timeout = float(timeout)


class TimeoutException(Exception):
    """Raised when a simulated request exceeds configured timeout."""


class HTTPStatusError(Exception):
    """Raised when a response status indicates an error."""

    def __init__(self, message: str, *, request: Request | None = None, response: Response | None = None) -> None:
        super().__init__(message)
        self.request = request
        self.response = response


class URL:
    """Very small URL helper capturing path and params."""

    def __init__(self, base_url: str, endpoint: str, params: Mapping[str, Any] | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self._params = dict(params or {})

    @property
    def path(self) -> str:
        return self._path

    @property
    def params(self) -> Mapping[str, Any]:
        return dict(self._params)

    def __str__(self) -> str:
        if self._params:
            return f"{self._base}{self._path}?{urlencode(self._params, doseq=True)}"
        return f"{self._base}{self._path}"


class Request:
    """Simplified request container passed to MockTransport handlers."""

    def __init__(
        self,
        method: str,
        base_url: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.method = method.upper()
        self.url = URL(base_url, endpoint, params)
        self.headers: Dict[str, str] = {k: v for k, v in (headers or {}).items()}
        self.content: bytes | None = None


class Response:
    """Simplified HTTP response supporting JSON/text accessors."""

    def __init__(
        self,
        status_code: int,
        *,
        json: Any | None = None,
        text: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = int(status_code)
        self._json = json
        headers_dict = {str(k): str(v) for k, v in (headers or {}).items()}
        if json is not None and not any(k.lower() == "content-type" for k in headers_dict):
            headers_dict["Content-Type"] = "application/json"
        if text is not None:
            self.text = text
        elif json is not None:
            self.text = json_module_dumps(json)
        else:
            self.text = ""
        self.headers: Dict[str, str] = headers_dict
        self.request: Request | None = None

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        if not self.text:
            return None
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPStatusError(f"HTTP {self.status_code}", request=self.request, response=self)


class AsyncBaseTransport:
    """Base transport interface for AsyncClient."""

    async def handle(self, request: Request) -> Response:  # pragma: no cover - interface contract
        raise NotImplementedError


class MockTransport(AsyncBaseTransport):
    """Transport using a user-provided handler callable."""

    def __init__(self, handler: Callable[[Request], Response | Awaitable[Response]]) -> None:
        self._handler = handler

    async def handle(self, request: Request) -> Response:
        result = self._handler(request)
        if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
            result = await result  # type: ignore[assignment]
        if not isinstance(result, Response):
            raise TypeError("MockTransport handler must return httpx.Response")
        return result


class AsyncClient:
    """Very small subset of httpx.AsyncClient used in tests."""

    def __init__(
        self,
        *,
        base_url: str = "",
        headers: Optional[Mapping[str, str]] = None,
        timeout: Timeout | None = None,
        transport: AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: Dict[str, str] = {k: v for k, v in (headers or {}).items()}
        self._timeout = timeout
        self._transport = transport or MockTransport(self._default_handler)

    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        merged_headers: Dict[str, str] = {**self._headers}
        if headers:
            merged_headers.update(headers)
        request = Request("GET", self._base_url, endpoint, params=params, headers=merged_headers)
        response = await self._transport.handle(request)
        response.request = request
        return response

    async def aclose(self) -> None:
        return None

    @staticmethod
    async def _default_handler(_: Request) -> Response:  # pragma: no cover - safety net
        raise TimeoutException("No transport handler configured")


def json_module_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)

