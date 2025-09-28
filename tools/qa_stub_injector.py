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
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable


_STUB_SENTINEL_ATTR = "__OFFLINE_STUB__"

_STATUS_CODES: dict[str, int] = {
    "HTTP_200_OK": 200,
    "HTTP_204_NO_CONTENT": 204,
    "HTTP_400_BAD_REQUEST": 400,
    "HTTP_404_NOT_FOUND": 404,
    "HTTP_422_UNPROCESSABLE_ENTITY": 422,
    "HTTP_500_INTERNAL_SERVER_ERROR": 500,
    "HTTP_503_SERVICE_UNAVAILABLE": 503,
}

_TESTCLIENT_HEALTH_PATHS = {"/health", "/healthz"}
_TESTCLIENT_READY_PATHS = {"/ready", "/readyz"}
_TESTCLIENT_WARMUP_PATHS = {"/__smoke__/warmup", "/smoke/warmup"}


class _HTTPStubResponse:
    def __init__(self, status_code: int = 204, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = dict(payload or {})
        self.text = "{}" if not self._payload else str(self._payload)

    def json(self) -> dict[str, Any]:
        return dict(self._payload)


def _install_status_module(name: str) -> ModuleType:
    def _populate(module: ModuleType) -> None:
        for attr, value in _STATUS_CODES.items():
            setattr(module, attr, value)

    module = _ensure_module(name, _populate)
    if getattr(module, _STUB_SENTINEL_ATTR, False):
        for attr, value in _STATUS_CODES.items():
            setattr(module, attr, value)
    return module


def _normalize_path(path: str) -> str:
    candidate = path.split("?")[0]
    while "//" in candidate:
        candidate = candidate.replace("//", "/")
    if not candidate.startswith("/"):
        candidate = f"/{candidate}"
    if len(candidate) > 1 and candidate.endswith("/"):
        candidate = candidate.rstrip("/")
    return candidate


def _dispatch_testclient_response(path: str) -> _HTTPStubResponse:
    normalized = _normalize_path(path)
    if normalized in _TESTCLIENT_HEALTH_PATHS:
        return _HTTPStubResponse(status_code=200, payload={"status": "ok"})
    if normalized in _TESTCLIENT_READY_PATHS:
        return _HTTPStubResponse(status_code=200, payload={"status": "ok"})
    if normalized in _TESTCLIENT_WARMUP_PATHS:
        return _HTTPStubResponse(status_code=200, payload={"warmed": [], "took_ms": 0})
    return _HTTPStubResponse(status_code=404, payload={"detail": "Not Found"})


def _maybe_patch_ssl_module() -> None:
    if os.getenv("QA_STUB_SSL") != "1":
        return

    current = sys.modules.get("ssl")
    if current is not None and not getattr(current, _STUB_SENTINEL_ATTR, False):
        return

    module = types.ModuleType("ssl")

    class SSLContext:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def wrap_socket(self, *_: Any, **__: Any) -> None:
            return None

        def load_verify_locations(self, *_: Any, **__: Any) -> None:
            return None


    module.SSLContext = SSLContext  # type: ignore[attr-defined]
    module.SSLError = SSLError  # type: ignore[attr-defined]
    module.SSLWantReadError = SSLWantReadError  # type: ignore[attr-defined]
    module.create_default_context = create_default_context  # type: ignore[attr-defined]
    module.wrap_socket = wrap_socket  # type: ignore[attr-defined]
    module.load_verify_locations = load_verify_locations  # type: ignore[attr-defined]

    setattr(module, _STUB_SENTINEL_ATTR, True)
    sys.modules["ssl"] = module


def _ensure_module(name: str, factory: Callable[[ModuleType], None]) -> ModuleType:
    if name in sys.modules and not getattr(sys.modules[name], _STUB_SENTINEL_ATTR, False):
        return sys.modules[name]

    module = sys.modules.get(name)
    if module is None or not getattr(module, _STUB_SENTINEL_ATTR, False):
        module = types.ModuleType(name)
        factory(module)
        setattr(module, _STUB_SENTINEL_ATTR, True)
        sys.modules[name] = module

    if "." in name:
        parent_name, _, child_name = name.rpartition(".")
        parent = _ensure_module(parent_name, lambda m: setattr(m, "__path__", []))
        setattr(parent, child_name, module)
        if not hasattr(parent, "__path__"):
            parent.__path__ = []  # type: ignore[attr-defined]

    return module


def _install_pydantic() -> None:
    existing = sys.modules.get("pydantic")
    if existing is not None and not getattr(existing, _STUB_SENTINEL_ATTR, False):
        return

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

    def field_validator(*fields: str, **__: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator

    module.BaseModel = BaseModel
    module.Field = Field
    module.ValidationError = ValidationError
    module.ConfigDict = ConfigDict
    module.computed_field = computed_field
    module.field_validator = field_validator

    settings_module = sys.modules.get("pydantic_settings")
    if settings_module is not None and not getattr(settings_module, _STUB_SENTINEL_ATTR, False):
        return

    settings_module = _ensure_module("pydantic_settings", lambda m: setattr(m, "__path__", []))
    settings_module.BaseSettings = BaseModel
    settings_module.SettingsConfigDict = dict


def _install_fastapi_testclient(module: ModuleType) -> None:
    if not getattr(module, _STUB_SENTINEL_ATTR, False):
        return

    testclient_module = _ensure_module("fastapi.testclient", lambda m: None)
    if not getattr(testclient_module, _STUB_SENTINEL_ATTR, False):
        return

    class TestClient:
        __OFFLINE_STUB__ = True

        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "TestClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, path: str, *_: Any, **__: Any) -> _HTTPStubResponse:
            return _dispatch_testclient_response(path)

        def post(self, path: str, *_: Any, **__: Any) -> _HTTPStubResponse:
            return _dispatch_testclient_response(path)

    testclient_module.TestClient = TestClient
    module.testclient = testclient_module


def _install_fastapi() -> None:
    existing = sys.modules.get("fastapi")
    if existing is not None and not getattr(existing, _STUB_SENTINEL_ATTR, False):
        return

    module = _ensure_module("fastapi", lambda m: None)
    setattr(module, "__OFFLINE_STUB__", True)

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: Any = None) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self) -> None:
            self.routes: list[dict[str, Any]] = []
            self.route_handlers: dict[str, dict[str, Any]] = {}

        def _add_route(self, path: str, methods: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                entry = self.route_handlers.setdefault(path, {"methods": set(), "endpoint": func})
                entry["methods"].update(methods)
                entry["endpoint"] = func
                self.routes.append({"path": path, "methods": list(entry["methods"]), "endpoint": func})
                return func

            return decorator

        def get(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._add_route(path, ["GET"])

        def post(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._add_route(path, ["POST"])

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: list[str] | None = None, **_: Any) -> None:
            method_list = methods or ["GET"]
            entry = self.route_handlers.setdefault(path, {"methods": set(), "endpoint": endpoint})
            entry["methods"].update(method_list)
            entry["endpoint"] = endpoint
            self.routes.append({"path": path, "methods": list(entry["methods"]), "endpoint": endpoint})

    class FastAPI:
        def __init__(self, *_, **__) -> None:
            self.router = APIRouter()
            self.routes: list[dict[str, Any]] = []
            self.route_handlers: dict[str, dict[str, Any]] = {}
            self._middleware_stack: list[tuple[Any, dict[str, Any]]] = []
            self._decorated_middlewares: list[tuple[str, Callable[..., Any]]] = []

        def _register(self, path: str, methods: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self.router._add_route(path, methods)

        def get(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._register(path, ["GET"])

        def post(self, path: str, **_) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._register(path, ["POST"])

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: list[str] | None = None, **_: Any) -> None:
            method_list = methods or ["GET"]
            entry = self.route_handlers.setdefault(path, {"methods": set(), "endpoint": endpoint})
            entry["methods"].update(method_list)
            entry["endpoint"] = endpoint
            self.routes.append({"path": path, "methods": list(entry["methods"]), "endpoint": endpoint})

        def include_router(self, router: APIRouter, **_: Any) -> None:
            self.routes.extend(router.routes)
            for path, info in router.route_handlers.items():
                entry = self.route_handlers.setdefault(path, {"methods": set(), "endpoint": info.get("endpoint")})
                entry["methods"].update(info.get("methods", set()))
                entry["endpoint"] = info.get("endpoint")

        def add_middleware(self, middleware_class: Any, **options: Any) -> None:
            self._middleware_stack.append((middleware_class, options))

        def middleware(self, _type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
                self._decorated_middlewares.append((_type, handler))
                return handler

            return decorator

    status_module = _install_status_module("fastapi.status")

    module.FastAPI = FastAPI
    module.APIRouter = APIRouter
    module.HTTPException = HTTPException
    class Response:
        def __init__(self, content: Any | None = None, status_code: int = 200) -> None:
            self.body = content
            self.status_code = status_code

    class Request:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.scope: dict[str, Any] = {}

    module.Response = Response
    module.Request = Request

    responses_module = _ensure_module("fastapi.responses", lambda m: None)
    if not getattr(responses_module, _STUB_SENTINEL_ATTR, False):
        return

    class JSONResponse(Response):
        def __init__(self, content: Any, status_code: int = 200) -> None:
            super().__init__(content=content, status_code=status_code)

    class PlainTextResponse(Response):
        def __init__(self, content: str, status_code: int = 200) -> None:
            super().__init__(content=content, status_code=status_code)

    responses_module.JSONResponse = JSONResponse
    responses_module.PlainTextResponse = PlainTextResponse
    module.responses = responses_module
    _install_fastapi_testclient(module)


def _install_starlette_testclient() -> None:
    existing = sys.modules.get("starlette")
    if existing is not None and not getattr(existing, _STUB_SENTINEL_ATTR, False):
        return

    def _factory(module: ModuleType) -> None:
        module.__path__ = []  # type: ignore[attr-defined]

    starlette_module = _ensure_module("starlette", _factory)
    testclient_module = _ensure_module("starlette.testclient", lambda m: None)
    if not getattr(testclient_module, _STUB_SENTINEL_ATTR, False):
        return
    starlette_module.testclient = testclient_module

    middleware_module = _ensure_module("starlette.middleware", lambda m: setattr(m, "__path__", []))
    base_module = _ensure_module("starlette.middleware.base", lambda m: None)

    class BaseHTTPMiddleware:
        def __init__(self, app: Any, *_: Any, **__: Any) -> None:
            self.app = app

        async def dispatch(self, request: Any, call_next: Callable[..., Any]) -> Any:
            return await call_next(request)

    base_module.BaseHTTPMiddleware = BaseHTTPMiddleware
    middleware_module.base = base_module
    starlette_module.middleware = middleware_module

    class TestClient:
        __OFFLINE_STUB__ = True

        def __init__(self, *_: Any, **__: Any) -> None:
            self._app = _[0] if _ else None

        def __enter__(self) -> "TestClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, path: str, *_: Any, **__: Any) -> _HTTPStubResponse:
            return _dispatch_testclient_response(path)

        def post(self, path: str, *_: Any, **__: Any) -> _HTTPStubResponse:
            return _dispatch_testclient_response(path)

    testclient_module.TestClient = TestClient


def _install_aiogram() -> None:
    existing = sys.modules.get("aiogram")
    if existing is not None and not getattr(existing, _STUB_SENTINEL_ATTR, False):
        return

    module = _ensure_module("aiogram", lambda m: setattr(m, "__path__", []))
    if not getattr(module, _STUB_SENTINEL_ATTR, False):
        return

    class Router:
        def __init__(self) -> None:
            self._handlers: list[Callable[..., Any]] = []

        def message(self, *_: Any, **__: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
                self._handlers.append(handler)
                return handler

            return decorator

        def callback_query(self, *_: Any, **__: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
                self._handlers.append(handler)
                return handler

            return decorator

        def include_router(self, router: "Router") -> None:
            self._handlers.extend(router._handlers)

    class Dispatcher:
        def __init__(self) -> None:
            self.routers: list[Any] = []

        def include_router(self, router: Any) -> None:
            self.routers.append(router)

    class Bot:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        async def send_message(self, *_: Any, **__: Any) -> None:
            return None

    class _FilterField:
        def __init__(self, name: str) -> None:
            self.name = name

        def __call__(self, *_: Any, **__: Any) -> bool:
            return True

        def __eq__(self, _other: Any) -> Callable[..., bool]:
            return lambda *_args, **_kwargs: True

        def startswith(self, _prefix: str) -> Callable[..., bool]:
            return lambda *_args, **_kwargs: True

    class _FilterBuilder:
        def __getattr__(self, name: str) -> _FilterField:
            return _FilterField(name)

    module.Router = Router
    module.Dispatcher = Dispatcher
    module.Bot = Bot
    module.F = _FilterBuilder()
    module.__all__ = ["Router", "Dispatcher", "Bot", "F"]

    class BaseMiddleware:
        async def __call__(self, handler: Callable[..., Any], event: Any, data: dict[str, Any]) -> Any:
            return await handler(event, data)

    module.BaseMiddleware = BaseMiddleware

    exceptions_module = _ensure_module("aiogram.exceptions", lambda m: None)

    class TelegramAPIError(Exception):
        pass

    class TelegramBadRequest(TelegramAPIError):
        pass

    exceptions_module.TelegramAPIError = TelegramAPIError
    exceptions_module.TelegramBadRequest = TelegramBadRequest

    filters_module = _ensure_module("aiogram.filters", lambda m: None)

    class Command:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __call__(self, handler: Callable[..., Any]) -> Callable[..., Any]:
            return handler

    @dataclass(slots=True)
    class CommandObject:
        command: str | None = None
        args: str | None = None

    filters_module.Command = Command
    filters_module.CommandObject = CommandObject

    types_module = _ensure_module("aiogram.types", lambda m: setattr(m, "__path__", []))

    @dataclass(slots=True)
    class User:
        id: int = 0

    @dataclass(slots=True)
    class Message:
        text: str | None = None
        from_user: User | None = None

        async def answer(self, *_: Any, **__: Any) -> None:
            return None

        async def reply(self, *_: Any, **__: Any) -> None:
            return None

        async def edit_text(self, *_: Any, **__: Any) -> None:
            return None

    @dataclass(slots=True)
    class CallbackQuery:
        data: str | None = None
        message: Message | None = None

        async def answer(self, *_: Any, **__: Any) -> None:
            return None

    @dataclass(slots=True)
    class FSInputFile:
        path: str
        filename: str | None = None

    @dataclass(slots=True)
    class InlineKeyboardButton:
        text: str
        callback_data: str | None = None

    @dataclass(slots=True)
    class InlineKeyboardMarkup:
        inline_keyboard: list[list[InlineKeyboardButton]] = field(default_factory=list)

    @dataclass(slots=True)
    class BotCommand:
        command: str
        description: str

    types_module.User = User
    types_module.Message = Message
    types_module.CallbackQuery = CallbackQuery
    types_module.FSInputFile = FSInputFile
    types_module.InlineKeyboardButton = InlineKeyboardButton
    types_module.InlineKeyboardMarkup = InlineKeyboardMarkup
    types_module.CommandObject = CommandObject
    types_module.BotCommand = BotCommand

    utils_module = _ensure_module("aiogram.utils", lambda m: setattr(m, "__path__", []))
    keyboard_module = _ensure_module("aiogram.utils.keyboard", lambda m: None)

    class InlineKeyboardBuilder:
        def __init__(self) -> None:
            self._rows: list[list[InlineKeyboardButton]] = []
            self.buttons: list[InlineKeyboardButton] = []

        def button(self, *, text: str, callback_data: str | None = None, **__: Any) -> None:
            button = InlineKeyboardButton(text=text, callback_data=callback_data)
            self.buttons.append(button)
            self._rows.append([button])

        def row(self, *buttons: InlineKeyboardButton) -> None:
            if buttons:
                self._rows.append(list(buttons))
                self.buttons.extend(buttons)

        def adjust(self, *_sizes: int) -> None:
            return None

        def as_markup(self) -> InlineKeyboardMarkup:
            if not self._rows:
                self._rows = [[button] for button in self.buttons]
            return InlineKeyboardMarkup(inline_keyboard=list(self._rows))

    keyboard_module.InlineKeyboardBuilder = InlineKeyboardBuilder
    utils_module.keyboard = keyboard_module

    client_module = _ensure_module("aiogram.client", lambda m: setattr(m, "__path__", []))
    default_module = _ensure_module("aiogram.client.default", lambda m: None)

    @dataclass(slots=True)
    class DefaultBotProperties:
        parse_mode: str | None = None

    default_module.DefaultBotProperties = DefaultBotProperties
    client_module.default = default_module

    enums_module = _ensure_module("aiogram.enums", lambda m: None)

    class _ParseMode:
        HTML = "HTML"
        MARKDOWN = "Markdown"

    enums_module.ParseMode = _ParseMode

    module.exceptions = exceptions_module
    module.filters = filters_module
    module.types = types_module
    module.utils = utils_module
    module.client = client_module
    module.enums = enums_module


def _install_redis_stub() -> None:
    module = _ensure_module("redis", lambda m: None)
    if not getattr(module, _STUB_SENTINEL_ATTR, False):
        return

    class Redis:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def ping(self) -> bool:
            return True

    StrictRedis = Redis
    namespace = types.SimpleNamespace(Redis=Redis, StrictRedis=StrictRedis)

    module.Redis = Redis  # type: ignore[attr-defined]
    module.StrictRedis = StrictRedis  # type: ignore[attr-defined]
    module.redis = namespace  # type: ignore[attr-defined]
    module.__all__ = ["Redis", "StrictRedis", "redis"]

    async_module = _ensure_module("redis.asyncio", lambda m: None)
    if getattr(async_module, _STUB_SENTINEL_ATTR, False):
        async_module.Redis = Redis  # type: ignore[attr-defined]
        async_module.StrictRedis = StrictRedis  # type: ignore[attr-defined]

    exceptions_module = _ensure_module("redis.exceptions", lambda m: None)
    if getattr(exceptions_module, _STUB_SENTINEL_ATTR, False):
        class RedisError(Exception):
            pass

        exceptions_module.RedisError = RedisError  # type: ignore[attr-defined]
        exceptions_module.ConnectionError = RedisError  # type: ignore[attr-defined]


def _install_http_stubs() -> None:
    def _make_request_stub(*_: Any, **__: Any) -> _HTTPStubResponse:
        return _HTTPStubResponse()

    def _attach_common_http_methods(module: ModuleType) -> None:
        for name in ("request", "get", "post", "put", "patch", "delete", "head", "options"):
            setattr(module, name, _make_request_stub)

    requests_module = _ensure_module("requests", lambda m: setattr(m, "__path__", []))
    if getattr(requests_module, _STUB_SENTINEL_ATTR, False):

        class Session:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            def request(self, *_: Any, **__: Any) -> _HTTPStubResponse:
                return _HTTPStubResponse()

            get = request
            post = request
            put = request
            patch = request
            delete = request
            head = request
            options = request

        requests_module.Session = Session  # type: ignore[attr-defined]
        requests_module.Response = _HTTPStubResponse  # type: ignore[attr-defined]
        _attach_common_http_methods(requests_module)

    urllib3_module = _ensure_module("urllib3", lambda m: setattr(m, "__path__", []))
    if getattr(urllib3_module, _STUB_SENTINEL_ATTR, False):

        class PoolManager:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            def request(self, *_: Any, **__: Any) -> _HTTPStubResponse:
                return _HTTPStubResponse()

        urllib3_module.PoolManager = PoolManager  # type: ignore[attr-defined]
        _attach_common_http_methods(urllib3_module)

    httpx_module = _ensure_module("httpx", lambda m: setattr(m, "__path__", []))
    if getattr(httpx_module, _STUB_SENTINEL_ATTR, False):

        class AsyncBaseTransport:
            pass

        class HTTPError(Exception):
            pass

        class TimeoutException(HTTPError):
            pass

        class HTTPStatusError(HTTPError):
            pass

        class Timeout:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

        class Response(_HTTPStubResponse):
            def __init__(self, status_code: int = 204, json_data: dict[str, Any] | None = None) -> None:
                super().__init__(status_code=status_code, payload=json_data or {})

        class Client:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            def request(self, *_: Any, **__: Any) -> Response:
                return Response()

            get = request
            post = request
            put = request
            patch = request
            delete = request
            head = request
            options = request

        class AsyncClient:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            async def __aenter__(self) -> "AsyncClient":
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def request(self, *_: Any, **__: Any) -> Response:
                return Response()

            async def get(self, *_: Any, **__: Any) -> Response:
                return Response()

            async def post(self, *_: Any, **__: Any) -> Response:
                return Response()

        httpx_module.AsyncBaseTransport = AsyncBaseTransport  # type: ignore[attr-defined]
        httpx_module.HTTPError = HTTPError  # type: ignore[attr-defined]
        httpx_module.TimeoutException = TimeoutException  # type: ignore[attr-defined]
        httpx_module.HTTPStatusError = HTTPStatusError  # type: ignore[attr-defined]
        httpx_module.Timeout = Timeout  # type: ignore[attr-defined]
        httpx_module.Response = Response  # type: ignore[attr-defined]
        httpx_module.AsyncClient = AsyncClient  # type: ignore[attr-defined]
        httpx_module.Client = Client  # type: ignore[attr-defined]
        httpx_module.codes = types.SimpleNamespace(NO_CONTENT=204)  # type: ignore[attr-defined]

        def _httpx_request(*_: Any, **__: Any) -> Response:
            return Response()

        for name in ("request", "get", "post", "put", "patch", "delete", "head", "options"):
            setattr(httpx_module, name, _httpx_request)


def _install_empty_module(name: str, *, is_package: bool = True) -> ModuleType:
    def _factory(module: ModuleType) -> None:
        if is_package:
            module.__path__ = []  # type: ignore[attr-defined]

    stub = _ensure_module(name, _factory)
    if is_package and not hasattr(stub, "__path__"):
        stub.__path__ = []  # type: ignore[attr-defined]
    return stub


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

    _maybe_patch_ssl_module()
    _install_pydantic()
    _install_fastapi()
    _install_starlette_testclient()
    _install_aiogram()
    _install_redis_stub()
    _install_http_stubs()

    for module_name in ("numpy", "pandas", "joblib", "sqlalchemy", "alembic"):
        _install_empty_module(module_name)

    _install_empty_module("pandas.api")
    _install_empty_module("pandas.api.types", is_package=False)
    _install_empty_module("sklearn")
    _install_empty_module("sklearn.metrics", is_package=False)
    _install_empty_module("sklearn.linear_model", is_package=False)
    _install_empty_module("sklearn.preprocessing", is_package=False)
    _install_empty_module("sklearn.model_selection", is_package=False)
    _install_empty_module("sklearn.calibration", is_package=False)
    _install_empty_module("sklearn.isotonic", is_package=False)
    _install_empty_module("sqlalchemy.engine", is_package=False)
    _install_empty_module("sqlalchemy.exc", is_package=False)
    _install_empty_module("sqlalchemy.ext", is_package=False)
    _install_empty_module("sqlalchemy.ext.asyncio", is_package=False)
    _install_empty_module("sqlalchemy.pool", is_package=False)
    _install_empty_module("asyncpg", is_package=False)
    _install_empty_module("aiohttp", is_package=False)
    _install_empty_module("matplotlib")
    _install_empty_module("matplotlib.pyplot", is_package=False)
    _install_empty_module("prometheus_client", is_package=False)
    _install_empty_module("alembic.command", is_package=False)
    _install_empty_module("alembic.config", is_package=False)
    _install_empty_module("sentry_sdk", is_package=False)

    sentry_module = sys.modules.get("sentry_sdk")

    def _noop(*_: Any, **__: Any) -> None:
        return None

    if sentry_module is not None and getattr(sentry_module, _STUB_SENTINEL_ATTR, False):
        sentry_module.init = _noop  # type: ignore[attr-defined]
        sentry_module.capture_message = _noop  # type: ignore[attr-defined]
        sentry_module.capture_exception = _noop  # type: ignore[attr-defined]

    pandas_api_types = sys.modules.get("pandas.api.types")
    if pandas_api_types is not None and getattr(pandas_api_types, _STUB_SENTINEL_ATTR, False):
        pandas_api_types.is_numeric_dtype = lambda *_: True  # type: ignore[attr-defined]

    linear_model_module = sys.modules.get("sklearn.linear_model")
    if linear_model_module is not None and getattr(linear_model_module, _STUB_SENTINEL_ATTR, False):

        class PoissonRegressor:
            def fit(self, *_: Any, **__: Any) -> "PoissonRegressor":
                return self

            def predict(self, *_: Any, **__: Any) -> list[float]:
                return []

        class Ridge:
            def fit(self, *_: Any, **__: Any) -> "Ridge":
                return self

            def predict(self, *_: Any, **__: Any) -> list[float]:
                return []

        linear_model_module.PoissonRegressor = PoissonRegressor  # type: ignore[attr-defined]
        linear_model_module.Ridge = Ridge  # type: ignore[attr-defined]

    preprocessing_module = sys.modules.get("sklearn.preprocessing")
    if preprocessing_module is not None and getattr(preprocessing_module, _STUB_SENTINEL_ATTR, False):

        class StandardScaler:
            def fit(self, *_: Any, **__: Any) -> "StandardScaler":
                return self

            def transform(self, data: Any, *_: Any, **__: Any) -> Any:
                return data

            def fit_transform(self, data: Any, *_: Any, **__: Any) -> Any:
                return data

        preprocessing_module.StandardScaler = StandardScaler  # type: ignore[attr-defined]

    metrics_module = sys.modules.get("sklearn.metrics")
    if metrics_module is not None and getattr(metrics_module, _STUB_SENTINEL_ATTR, False):
        metrics_module.log_loss = lambda *_: 0.0  # type: ignore[attr-defined]
        metrics_module.roc_auc_score = lambda *_: 0.0  # type: ignore[attr-defined]

    model_selection_module = sys.modules.get("sklearn.model_selection")
    if model_selection_module is not None and getattr(model_selection_module, _STUB_SENTINEL_ATTR, False):

        class TimeSeriesSplit:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            def split(self, *_: Any, **__: Any):
                yield [], []

        model_selection_module.TimeSeriesSplit = TimeSeriesSplit  # type: ignore[attr-defined]

    calibration_module = sys.modules.get("sklearn.calibration")
    if calibration_module is not None and getattr(calibration_module, _STUB_SENTINEL_ATTR, False):
        calibration_module.calibration_curve = lambda *_: ([], [])  # type: ignore[attr-defined]

    isotonic_module = sys.modules.get("sklearn.isotonic")
    if isotonic_module is not None and getattr(isotonic_module, _STUB_SENTINEL_ATTR, False):

        class IsotonicRegression:
            def fit(self, *_: Any, **__: Any) -> "IsotonicRegression":
                return self

            def predict(self, *_: Any, **__: Any) -> list[float]:
                return []

        isotonic_module.IsotonicRegression = IsotonicRegression  # type: ignore[attr-defined]

    numpy_module = sys.modules.get("numpy")
    if numpy_module is not None and getattr(numpy_module, _STUB_SENTINEL_ATTR, False):
        numpy_module.float64 = float  # type: ignore[attr-defined]
        numpy_module.int64 = int  # type: ignore[attr-defined]
        numpy_module.ndarray = list  # type: ignore[attr-defined]
        numpy_module.array = lambda data=None, *_: list(data or [])  # type: ignore[attr-defined]
        numpy_module.log = lambda value: value  # type: ignore[attr-defined]
        numpy_module.exp = lambda value: value  # type: ignore[attr-defined]
        numpy_module.mean = lambda *_: 0.0  # type: ignore[attr-defined]

    pandas_module = sys.modules.get("pandas")
    if pandas_module is not None and getattr(pandas_module, _STUB_SENTINEL_ATTR, False):

        class DataFrame(dict):
            def copy(self, *_: Any, **__: Any) -> "DataFrame":
                return DataFrame(self)

            def merge(self, *_: Any, **__: Any) -> "DataFrame":
                return DataFrame()

            def rename(self, *_: Any, **__: Any) -> "DataFrame":
                return self

            def sort_values(self, *_: Any, **__: Any) -> "DataFrame":
                return self

            def reset_index(self, *_: Any, **__: Any) -> "DataFrame":
                return self

            def drop(self, *_: Any, **__: Any) -> "DataFrame":
                return self

            def insert(self, *_: Any, **__: Any) -> None:
                return None

            def loc(self, *_: Any, **__: Any) -> "DataFrame":
                return self

            def to_numpy(self, *_: Any, **__: Any) -> list[Any]:
                return []

            def astype(self, *_: Any, **__: Any) -> "DataFrame":
                return self

        class Series(list):
            def to_numpy(self, *_: Any, **__: Any) -> list[Any]:
                return list(self)

            def astype(self, *_: Any, **__: Any) -> "Series":
                return self

        pandas_module.DataFrame = DataFrame  # type: ignore[attr-defined]
        pandas_module.Series = Series  # type: ignore[attr-defined]
        pandas_module.read_csv = lambda *_: DataFrame()  # type: ignore[attr-defined]
        pandas_module.read_parquet = lambda *_: DataFrame()  # type: ignore[attr-defined]

    alembic_module = sys.modules.get("alembic")
    if alembic_module is not None and getattr(alembic_module, _STUB_SENTINEL_ATTR, False):
        command_module = sys.modules.get("alembic.command")
        config_module = sys.modules.get("alembic.config")

        if command_module is not None and getattr(command_module, _STUB_SENTINEL_ATTR, False):
            command_module.upgrade = _noop  # type: ignore[attr-defined]
            command_module.downgrade = _noop  # type: ignore[attr-defined]
            alembic_module.command = command_module  # type: ignore[attr-defined]

        if config_module is not None and getattr(config_module, _STUB_SENTINEL_ATTR, False):

            class Config:
                def __init__(self, *_: Any, **__: Any) -> None:
                    pass

            config_module.Config = Config  # type: ignore[attr-defined]
            alembic_module.config = config_module  # type: ignore[attr-defined]

    sqlalchemy_module = sys.modules.get("sqlalchemy")
    if sqlalchemy_module is not None and getattr(sqlalchemy_module, _STUB_SENTINEL_ATTR, False):
        sqlalchemy_module.text = lambda sql, *_: sql  # type: ignore[attr-defined]

    engine_module = sys.modules.get("sqlalchemy.engine")
    if engine_module is not None and getattr(engine_module, _STUB_SENTINEL_ATTR, False):

        class URL:
            def __init__(self, *_: Any, **__: Any) -> None:
                self.drivername = ""

        engine_module.URL = URL  # type: ignore[attr-defined]

        def make_url(*_: Any, **__: Any) -> URL:
            return URL()

        engine_module.make_url = make_url  # type: ignore[attr-defined]

    exc_module = sys.modules.get("sqlalchemy.exc")
    if exc_module is not None and getattr(exc_module, _STUB_SENTINEL_ATTR, False):

        class SQLAlchemyError(Exception):
            pass

        exc_module.SQLAlchemyError = SQLAlchemyError  # type: ignore[attr-defined]

    ext_asyncio_module = sys.modules.get("sqlalchemy.ext.asyncio")
    if ext_asyncio_module is not None and getattr(ext_asyncio_module, _STUB_SENTINEL_ATTR, False):

        class AsyncSession:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            async def __aenter__(self) -> "AsyncSession":
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def execute(self, *_: Any, **__: Any) -> None:
                return None

        class AsyncEngine:
            async def dispose(self, *_: Any, **__: Any) -> None:
                return None

        def create_async_engine(*_: Any, **__: Any) -> AsyncEngine:
            return AsyncEngine()

        def async_sessionmaker(*_: Any, **__: Any):
            def _factory(*args: Any, **kwargs: Any) -> AsyncSession:
                return AsyncSession()

            return _factory

        ext_asyncio_module.AsyncSession = AsyncSession  # type: ignore[attr-defined]
        ext_asyncio_module.AsyncEngine = AsyncEngine  # type: ignore[attr-defined]
        ext_asyncio_module.create_async_engine = create_async_engine  # type: ignore[attr-defined]
        ext_asyncio_module.async_sessionmaker = async_sessionmaker  # type: ignore[attr-defined]

    pool_module = sys.modules.get("sqlalchemy.pool")
    if pool_module is not None and getattr(pool_module, _STUB_SENTINEL_ATTR, False):

        class NullPool:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

        pool_module.NullPool = NullPool  # type: ignore[attr-defined]

    asyncpg_module = sys.modules.get("asyncpg")
    if asyncpg_module is not None and getattr(asyncpg_module, _STUB_SENTINEL_ATTR, False):

        class _AsyncPGConnection:
            async def fetch(self, *_: Any, **__: Any) -> list[Any]:
                return []

            async def execute(self, *_: Any, **__: Any) -> str:
                return "OK"

            async def close(self) -> None:
                return None

        async def connect(*_: Any, **__: Any) -> _AsyncPGConnection:
            return _AsyncPGConnection()

        asyncpg_module.connect = connect  # type: ignore[attr-defined]
        asyncpg_module.Connection = _AsyncPGConnection  # type: ignore[attr-defined]

    aiohttp_module = sys.modules.get("aiohttp")
    if aiohttp_module is not None and getattr(aiohttp_module, _STUB_SENTINEL_ATTR, False):

        class _AiohttpResponse:
            status = 200

            async def json(self) -> dict[str, Any]:
                return {}

            async def text(self) -> str:
                return ""

        class ClientSession:
            async def __aenter__(self) -> "ClientSession":
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def get(self, *_: Any, **__: Any) -> _AiohttpResponse:
                return _AiohttpResponse()

            async def post(self, *_: Any, **__: Any) -> _AiohttpResponse:
                return _AiohttpResponse()

        aiohttp_module.ClientSession = ClientSession  # type: ignore[attr-defined]

    httpx_module = sys.modules.get("httpx")
    if httpx_module is not None and getattr(httpx_module, _STUB_SENTINEL_ATTR, False):

        class AsyncBaseTransport:
            pass

        class HTTPError(Exception):
            pass

        class TimeoutException(HTTPError):
            pass

        class HTTPStatusError(HTTPError):
            pass

        class Timeout:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

        class _Response:
            def __init__(self, status_code: int = 200, json_data: dict[str, Any] | None = None) -> None:
                self.status_code = status_code
                self._json = json_data or {}
                self.headers: dict[str, Any] = {}
                self.text = "{}"

            def json(self) -> dict[str, Any]:
                return dict(self._json)

        class AsyncClient:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            async def get(self, *_: Any, **__: Any) -> _Response:
                return _Response()

            async def post(self, *_: Any, **__: Any) -> _Response:
                return _Response()

            async def request(self, *_: Any, **__: Any) -> _Response:
                return _Response()

            async def __aenter__(self) -> "AsyncClient":
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def close(self) -> None:
                return None

        httpx_module.AsyncClient = AsyncClient  # type: ignore[attr-defined]
        httpx_module.AsyncBaseTransport = AsyncBaseTransport  # type: ignore[attr-defined]
        httpx_module.HTTPError = HTTPError  # type: ignore[attr-defined]
        httpx_module.TimeoutException = TimeoutException  # type: ignore[attr-defined]
        httpx_module.HTTPStatusError = HTTPStatusError  # type: ignore[attr-defined]
        httpx_module.Timeout = Timeout  # type: ignore[attr-defined]
        httpx_module.Response = _Response  # type: ignore[attr-defined]
        httpx_module.codes = types.SimpleNamespace(NOT_MODIFIED=304)  # type: ignore[attr-defined]

    matplotlib_module = sys.modules.get("matplotlib")
    if matplotlib_module is not None and getattr(matplotlib_module, _STUB_SENTINEL_ATTR, False):

        def _matplotlib_use(*_: Any, **__: Any) -> None:
            return None

        matplotlib_module.use = _matplotlib_use  # type: ignore[attr-defined]
        pyplot_module = sys.modules.get("matplotlib.pyplot")
        if pyplot_module is not None and getattr(pyplot_module, _STUB_SENTINEL_ATTR, False):

            def figure(*_: Any, **__: Any) -> object:
                return object()

            def plot(*_: Any, **__: Any) -> None:
                return None

            def savefig(*_: Any, **__: Any) -> None:
                return None

            def close(*_: Any, **__: Any) -> None:
                return None

            def subplots(*_: Any, **__: Any) -> tuple[object, object]:
                return object(), object()

            pyplot_module.figure = figure  # type: ignore[attr-defined]
            pyplot_module.plot = plot  # type: ignore[attr-defined]
            pyplot_module.savefig = savefig  # type: ignore[attr-defined]
            pyplot_module.close = close  # type: ignore[attr-defined]
            pyplot_module.subplots = subplots  # type: ignore[attr-defined]
            matplotlib_module.pyplot = pyplot_module  # type: ignore[attr-defined]

    prometheus_module = sys.modules.get("prometheus_client")
    if prometheus_module is not None and getattr(prometheus_module, _STUB_SENTINEL_ATTR, False):

        class _Metric:
            def labels(self, *_: Any, **__: Any) -> "_Metric":
                return self

            def inc(self, *_: Any, **__: Any) -> None:
                return None

            def set(self, *_: Any, **__: Any) -> None:
                return None

            def observe(self, *_: Any, **__: Any) -> None:
                return None

        def _metric_factory(*_: Any, **__: Any) -> _Metric:
            return _Metric()

        prometheus_module.Counter = _metric_factory  # type: ignore[attr-defined]
        prometheus_module.Gauge = _metric_factory  # type: ignore[attr-defined]
        prometheus_module.Histogram = _metric_factory  # type: ignore[attr-defined]
        prometheus_module.CONTENT_TYPE_LATEST = "text/plain"  # type: ignore[attr-defined]
        prometheus_module.generate_latest = lambda *_: b"{}"  # type: ignore[attr-defined]
        prometheus_module.start_http_server = _noop  # type: ignore[attr-defined]

    try:
        import ml.calibration as calibration_module  # type: ignore[import-not-found]
    except Exception:
        calibration_module = None

    if calibration_module is not None:

        def _calibration_passthrough(probabilities: Any, *args: Any, **kwargs: Any) -> Any:
            return probabilities

        if not hasattr(calibration_module, "apply_calibration"):
            calibration_module.apply_calibration = _calibration_passthrough  # type: ignore[attr-defined]
        if not hasattr(calibration_module, "calibrate_probs"):
            calibration_module.calibrate_probs = _calibration_passthrough  # type: ignore[attr-defined]

    try:
        import ml.modifiers_model as modifiers_module  # type: ignore[import-not-found]
    except Exception:
        modifiers_module = None

    if modifiers_module is not None and not hasattr(modifiers_module, "CalibrationLayer"):

        class CalibrationLayer:
            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            def fit(self, *_: Any, **__: Any) -> "CalibrationLayer":
                return self

            def transform(self, data: Any, *_: Any, **__: Any) -> Any:
                return data

            def save(self, *_: Any, **__: Any) -> None:
                return None

        modifiers_module.CalibrationLayer = CalibrationLayer  # type: ignore[attr-defined]

    install_stubs._already_installed = True


__all__ = ["install_stubs"]
