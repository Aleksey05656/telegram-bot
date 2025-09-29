"""
@file: tests/conftest.py
@description: Pytest fixtures with numpy/pandas guard, asyncio fallback runner and stub loaders
@dependencies: app/config.py, tests/_stubs, tests/conftest_np_guard.py, asyncio
@created: 2025-09-10
"""

"""
@file: tests/conftest.py
@description: Pytest fixtures with numpy/pandas guard, asyncio fallback runner and stub loaders
@dependencies: app/config.py, tests/_stubs, tests/conftest_np_guard.py, asyncio
@created: 2025-09-10
"""

import asyncio
import importlib.util
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from tests._stubs import ensure_stubs

pytest_plugins = ["conftest_np_guard"]

FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
ALEMBIC_AVAILABLE = importlib.util.find_spec("alembic") is not None


# Ensure offline stubs are visible only when optional dependencies are missing or
# when the USE_OFFLINE_STUBS toggle is explicitly enabled.
ensure_stubs(
    [
        "pydantic",
        "fastapi",
        "httpx",
        "aiogram",
        "prometheus_client",
        "redis",
        "rq",
        "starlette",
        "sentry_sdk",
        "numpy",
        "pandas",
        "sqlalchemy",
        "joblib",
    ]
)


# Автоматически включаем STUB-режим SportMonks для тестов,
# если ключ отсутствует или равен "dummy".
@pytest.fixture(autouse=True, scope="session")
def _force_sportmonks_stub():
    key = os.getenv("SPORTMONKS_API_KEY", "")
    if (not key) or (key.lower() == "dummy"):
        os.environ["SPORTMONKS_STUB"] = "1"
    return


from app import config as cfg  # noqa: E402


@pytest.fixture(autouse=True)
def _force_prometheus_enabled(monkeypatch):
    monkeypatch.setenv("PROMETHEUS__ENABLED", "true")
    if hasattr(cfg, "reset_settings_cache"):
        cfg.reset_settings_cache()
    return


@pytest.fixture(autouse=True)
def _defaults_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", os.getenv("APP_NAME", "ml-service"))
    monkeypatch.setenv("DEBUG", os.getenv("DEBUG", "false"))
    return


def pytest_pyfunc_call(pyfuncitem):
    """Execute async test functions via a local event loop if pytest-asyncio is unavailable."""

    test_obj = pyfuncitem.obj
    if asyncio.iscoroutinefunction(test_obj):
        argnames = getattr(pyfuncitem._fixtureinfo, "argnames", ())
        kwargs = {name: pyfuncitem.funcargs[name] for name in argnames}
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(test_obj(**kwargs))
        finally:
            loop.close()
        return True
    return None


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark async test for the local loop runner")
    config.addinivalue_line("markers", "requires_fastapi: test depends on FastAPI stack")
    config.addinivalue_line("markers", "requires_alembic: test depends on Alembic stack")


def pytest_addoption(parser):
    """Register compatibility ini options expected by pytest-asyncio."""

    parser.addini(
        "asyncio_mode",
        (
            "Compatibility shim for environments without pytest-asyncio where the "
            "ini option is still referenced."
        ),
        default="auto",
    )


def pytest_collection_modifyitems(config, items):
    del config  # unused but required by pytest signature

    if not FASTAPI_AVAILABLE:
        skip_fastapi = pytest.mark.skip(reason="FastAPI is not installed")
        for item in items:
            if item.get_closest_marker("requires_fastapi"):
                item.add_marker(skip_fastapi)

    if not ALEMBIC_AVAILABLE:
        skip_alembic = pytest.mark.skip(reason="Alembic is not installed")
        for item in items:
            if item.get_closest_marker("requires_alembic"):
                item.add_marker(skip_alembic)
