"""
/**
 * @file: fastapi_compat.py
 * @description: Provides FastAPI/Starlette shims for environments without runtime dependencies.
 * @dependencies: fastapi (optional), starlette (optional), asyncio
 * @created: 2025-10-31
 */
"""

from __future__ import annotations

import asyncio
import inspect
import json
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Optional, Tuple

try:  # pragma: no cover - prefer real FastAPI stack
    from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
    from fastapi.responses import JSONResponse, PlainTextResponse
    from fastapi.testclient import TestClient
    from starlette.middleware.base import BaseHTTPMiddleware

    FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover - fallback to lightweight shims
    FASTAPI_AVAILABLE = False
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))

    try:  # pragma: no cover - reuse offline stubs when available
        from tests._stubs.fastapi import (  # type: ignore[import-not-found]
            APIRouter as APIRouter,  # noqa: F401 - re-exported
            FastAPI as FastAPI,
            HTTPException as HTTPException,
            Request as Request,
            Response as Response,
            status as status,
        )
        from tests._stubs.fastapi.responses import (  # type: ignore[import-not-found]
            JSONResponse as JSONResponse,
            PlainTextResponse as PlainTextResponse,
        )
        from tests._stubs.fastapi.testclient import (  # type: ignore[import-not-found]
            TestClient as TestClient,
        )

        class BaseHTTPMiddleware:  # pragma: no cover - stubbed middleware
            def __init__(self, app: Any) -> None:
                self.app = app

            async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Any:
                return await call_next(request)

        __all__ = [
            "APIRouter",
            "BaseHTTPMiddleware",
            "FastAPI",
            "HTTPException",
            "JSONResponse",
            "PlainTextResponse",
            "Request",
            "Response",
            "TestClient",
            "status",
            "FASTAPI_AVAILABLE",
        ]

    except Exception:  # pragma: no cover - define inline shims
        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: Any | None = None) -> None:
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        class Response:
            def __init__(
                self,
                *,
                content: Any = None,
                status_code: int = 200,
                media_type: str | None = None,
            ) -> None:
                self.content = content
                self.status_code = status_code
                self.media_type = media_type
                self.headers: dict[str, str] = {}
                if media_type:
                    self.headers["content-type"] = media_type

        class JSONResponse(Response):
            def __init__(self, content: Any, status_code: int = 200) -> None:
                super().__init__(content=content, status_code=status_code, media_type="application/json")

        class PlainTextResponse(Response):
            def __init__(self, content: str, status_code: int = 200) -> None:
                super().__init__(content=content, status_code=status_code, media_type="text/plain; charset=utf-8")

        class Request:  # pragma: no cover - placeholder for middleware signatures
            def __init__(self, scope: Optional[dict[str, Any]] = None) -> None:
                self.scope = scope or {}
                self.headers: dict[str, str] = {}

        class _Status(SimpleNamespace):
            HTTP_200_OK = 200
            HTTP_204_NO_CONTENT = 204
            HTTP_404_NOT_FOUND = 404
            HTTP_422_UNPROCESSABLE_ENTITY = 422
            HTTP_500_INTERNAL_SERVER_ERROR = 500
            HTTP_503_SERVICE_UNAVAILABLE = 503

        status = _Status()  # type: ignore[assignment]

        _Route = dict[str, Any]

        class APIRouter:
            def __init__(self) -> None:
                self.routes: list[_Route] = []

            def get(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                return self._register(path, methods=["GET"], **kwargs)

            def add_api_route(
                self,
                path: str,
                endpoint: Callable[..., Any],
                *,
                methods: Optional[Iterable[str]] = None,
                tags: Optional[Iterable[str]] = None,
                **__: Any,
            ) -> None:
                method_list = [m.upper() for m in (methods or ["GET"])]
                self.routes.append(
                    {
                        "path": path,
                        "methods": method_list,
                        "endpoint": endpoint,
                        "tags": list(tags or []),
                    }
                )

            def _register(
                self,
                path: str,
                *,
                methods: Iterable[str],
                tags: Optional[Iterable[str]] = None,
                **__: Any,
            ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                normalized_methods = [m.upper() for m in methods]

                def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                    self.routes.append(
                        {
                            "path": path,
                            "methods": normalized_methods,
                            "endpoint": func,
                            "tags": list(tags or []),
                        }
                    )
                    return func

                return decorator

        class BaseHTTPMiddleware:  # pragma: no cover - request lifecycle not used offline
            def __init__(self, app: Any) -> None:
                self.app = app

            async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Any:
                return await call_next(request)

        class FastAPI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self._routes: list[_Route] = []
                self.routes: dict[str, Callable[..., Any]] = {}
                self._middleware: list[Tuple[type, tuple[Any, ...], dict[str, Any]]] = []

            def _store_route(
                self,
                path: str,
                methods: Iterable[str],
                endpoint: Callable[..., Any],
                tags: Optional[Iterable[str]] = None,
            ) -> None:
                normalized_methods = [m.upper() for m in methods]
                record = {
                    "path": path,
                    "methods": normalized_methods,
                    "endpoint": endpoint,
                    "tags": list(tags or []),
                }
                self._routes.append(record)
                if "GET" in normalized_methods:
                    self.routes[path] = endpoint

            def include_router(self, router: Any, *, prefix: str = "", tags: Optional[Iterable[str]] = None, **__: Any) -> None:
                router_routes = getattr(router, "routes", [])
                for route in router_routes:
                    path = prefix + route.get("path", "")
                    methods = [m.upper() for m in route.get("methods", ["GET"])]
                    endpoint = route.get("endpoint")
                    route_tags = list(route.get("tags", []))
                    if tags:
                        route_tags.extend(tags)
                    self._store_route(path, methods, endpoint, tags=route_tags)

            def add_middleware(self, middleware_class: type, *args: Any, **kwargs: Any) -> None:
                self._middleware.append((middleware_class, args, kwargs))

            def middleware(self, _event_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                return decorator

            def get(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                return self._register(path, methods=["GET"], **kwargs)

            def _register(
                self,
                path: str,
                *,
                methods: Iterable[str],
                tags: Optional[Iterable[str]] = None,
                **__: Any,
            ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                    self._store_route(path, methods, func, tags=tags)
                    return func

                return decorator

            def __getattr__(self, name: str) -> Any:
                if name.lower() in {"post", "put", "delete", "patch", "options"}:
                    return self._register
                raise AttributeError(name)

        class _ClientResponse:
            def __init__(self, status_code: int, payload: Any) -> None:
                self.status_code = status_code
                self._payload = payload

            def json(self) -> Any:
                return self._payload

            @property
            def text(self) -> str:
                if isinstance(self._payload, (dict, list)):
                    return json.dumps(self._payload)
                return str(self._payload)

        class TestClient:
            def __init__(self, app: FastAPI) -> None:
                self.app = app

            def get(self, path: str, **__: Any) -> _ClientResponse:
                return self._request("GET", path)

            def _request(self, method: str, path: str) -> _ClientResponse:
                route = self._find_route(method.upper(), path)
                if route is None:
                    return _ClientResponse(404, {"detail": "Not Found"})

                endpoint = route.get("endpoint")
                result = endpoint()
                if inspect.isawaitable(result):
                    result = asyncio.run(result)

                if isinstance(result, Response):
                    status_code = result.status_code or 200
                    content = result.content
                    if result.media_type and "json" in result.media_type and isinstance(content, (bytes, str)):
                        try:
                            content = json.loads(content if isinstance(content, str) else content.decode("utf-8"))
                        except Exception:
                            pass
                    return _ClientResponse(status_code, content)

                if isinstance(result, dict):
                    return _ClientResponse(200, result)

                return _ClientResponse(200, result)

            def _find_route(self, method: str, path: str) -> Optional[_Route]:
                normalized_path = path if path.startswith("/") else f"/{path}"
                for route in getattr(self.app, "_routes", []):
                    if normalized_path == route.get("path") and method in route.get("methods", []):
                        return route
                return None

        __all__ = [
            "APIRouter",
            "BaseHTTPMiddleware",
            "FastAPI",
            "HTTPException",
            "JSONResponse",
            "PlainTextResponse",
            "Request",
            "Response",
            "TestClient",
            "status",
            "FASTAPI_AVAILABLE",
        ]
else:  # pragma: no cover - re-export real implementations
    __all__ = [
        "APIRouter",
        "BaseHTTPMiddleware",
        "FastAPI",
        "HTTPException",
        "JSONResponse",
        "PlainTextResponse",
        "Request",
        "Response",
        "TestClient",
        "status",
        "FASTAPI_AVAILABLE",
    ]

if not FASTAPI_AVAILABLE:
    import sys
    from types import ModuleType

    def _install_stub_module(name: str, attrs: dict[str, Any]) -> ModuleType:
        module = ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        setattr(module, "__OFFLINE_STUB__", True)
        sys.modules[name] = module
        return module

    _install_stub_module(
        "fastapi",
        {
            "FastAPI": FastAPI,
            "HTTPException": HTTPException,
            "Request": Request,
            "Response": Response,
            "status": status,
        },
    )
    responses_module = _install_stub_module(
        "fastapi.responses",
        {
            "JSONResponse": JSONResponse,
            "PlainTextResponse": PlainTextResponse,
        },
    )
    testclient_module = _install_stub_module("fastapi.testclient", {"TestClient": TestClient})

    root_module = sys.modules.get("fastapi")
    if root_module is not None:
        setattr(root_module, "responses", responses_module)
        setattr(root_module, "testclient", testclient_module)

__all__ = sorted(__all__)
