"""
@file: tools/qa_stub_injector.py
@description: Runtime stub injector for offline QA workflows
@dependencies: os, sys
@created: 2024-05-09
"""

from __future__ import annotations

import os
import types
import sys
from types import ModuleType
from typing import Any, Callable


_STUB_SENTINEL_ATTR = "__OFFLINE_STUB__"


def _ensure_module(name: str, factory: Callable[[ModuleType], None]) -> ModuleType:
    if name in sys.modules and not getattr(sys.modules[name], _STUB_SENTINEL_ATTR, False):
        return sys.modules[name]

    module = sys.modules.get(name)
    if module is None or not getattr(module, _STUB_SENTINEL_ATTR, False):
        module = types.ModuleType(name)
        factory(module)
        setattr(module, _STUB_SENTINEL_ATTR, True)
        sys.modules[name] = module
    return module


def _install_pydantic() -> None:
    module = _ensure_module("pydantic", lambda m: None)

    class BaseModel:
        __slots__ = ("__data__",)

        def __init__(self, **data: Any) -> None:
            self.__data__ = data
            for key, value in data.items():
                setattr(self, key, value)

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> "BaseModel":
            return cls(**data)

        def model_dump(self, *_, **__) -> dict[str, Any]:
            return dict(self.__data__)

        def dict(self, *_, **__) -> dict[str, Any]:
            return self.model_dump()

    def Field(*_, **kwargs: Any) -> Any:  # noqa: N802 - mimic Pydantic API
        return kwargs.get("default", None)

    class ValidationError(Exception):
        pass

    ConfigDict = dict

    def computed_field(*_, **__):
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator

    module.BaseModel = BaseModel
    module.Field = Field
    module.ValidationError = ValidationError
    module.ConfigDict = ConfigDict
    module.computed_field = computed_field

    settings_module = _ensure_module("pydantic_settings", lambda m: None)
    settings_module.BaseSettings = BaseModel


def _install_fastapi() -> None:
    module = _ensure_module("fastapi", lambda m: None)

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: Any = None) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class _Status:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_204_NO_CONTENT = 204
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_422_UNPROCESSABLE_ENTITY = 422
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    class APIRouter:
        def __init__(self) -> None:
            self.routes: list[dict[str, Any]] = []

        def _add_route(self, path: str, methods: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.routes.append({"path": path, "methods": methods, "endpoint": func})
                return func

            return decorator

        def get(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._add_route(path, ["GET"])

        def post(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._add_route(path, ["POST"])

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: list[str] | None = None, **_: Any) -> None:
            self.routes.append({"path": path, "methods": methods or ["GET"], "endpoint": endpoint})

    class FastAPI:
        def __init__(self, *_, **__) -> None:
            self.router = APIRouter()
            self.routes: list[dict[str, Any]] = []

        def _register(self, path: str, methods: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self.router._add_route(path, methods)

        def get(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._register(path, ["GET"])

        def post(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._register(path, ["POST"])

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: list[str] | None = None, **_: Any) -> None:
            self.routes.append({"path": path, "methods": methods or ["GET"], "endpoint": endpoint})

        def include_router(self, router: APIRouter, **_: Any) -> None:
            self.routes.extend(router.routes)

    module.FastAPI = FastAPI
    module.APIRouter = APIRouter
    module.HTTPException = HTTPException
    module.status = _Status()


def _install_starlette_testclient() -> None:
    starlette_module = _ensure_module("starlette", lambda m: None)
    testclient_module = _ensure_module("starlette.testclient", lambda m: None)
    starlette_module.testclient = testclient_module

    class _StubResponse:
        def __init__(self) -> None:
            self.status_code = 204
            self._payload = {"skipped": "fastapi not installed"}
            self.text = "{}"

        def json(self) -> dict[str, Any]:
            return dict(self._payload)

    class TestClient:
        __OFFLINE_STUB__ = True

        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "TestClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, *_: Any, **__: Any) -> _StubResponse:
            return _StubResponse()

    testclient_module.TestClient = TestClient


def _install_empty_module(name: str) -> None:
    _ensure_module(name, lambda m: None)


def install_stubs() -> None:
    """
    If USE_OFFLINE_STUBS=1, inject minimal stub modules into sys.modules
    for imports: pydantic, pydantic_settings, fastapi, starlette.testclient,
    numpy, pandas, joblib, sqlalchemy, alembic. Only what's needed at import-time.
    No network/IO. Safe to call multiple times.
    """

    if os.getenv("USE_OFFLINE_STUBS") != "1":
        return

    if getattr(install_stubs, "_already_installed", False):
        return

    _install_pydantic()
    _install_fastapi()
    _install_starlette_testclient()

    for module_name in ("numpy", "pandas", "joblib", "sqlalchemy", "alembic"):
        _install_empty_module(module_name)

    install_stubs._already_installed = True


__all__ = ["install_stubs"]
