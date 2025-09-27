"""
@file: test_readiness.py
@description: Readiness endpoint behaviour tests.
@dependencies: app.api
@created: 2025-09-30
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import api
from app.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    from app.runtime_state import STATE

    original = (STATE.db_ready, STATE.polling_ready, STATE.scheduler_ready)
    STATE.db_ready = False
    STATE.polling_ready = False
    STATE.scheduler_ready = False
    yield
    STATE.db_ready, STATE.polling_ready, STATE.scheduler_ready = original


def _client() -> TestClient:
    return TestClient(api.app)


def test_readyz_ok(monkeypatch):
    async def pg_ok(*_args, **_kwargs):
        return "ok", None

    async def redis_ok(*_args, **_kwargs):
        return "ok", None

    def runtime_ok():
        return "ok", None

    monkeypatch.setattr(api, "_check_postgres", pg_ok)
    monkeypatch.setattr(api, "_check_redis", redis_ok)
    monkeypatch.setattr(api, "_check_runtime_flags", runtime_ok)

    resp = _client().get("/readyz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["postgres"]["status"] == "ok"


def test_readyz_degraded_runtime(monkeypatch):
    async def pg_ok(*_args, **_kwargs):
        return "ok", None

    async def redis_skip(*_args, **_kwargs):
        return "skipped", "redis url not configured"

    def runtime_degraded():
        return "degraded", "not ready: polling"

    monkeypatch.setattr(api, "_check_postgres", pg_ok)
    monkeypatch.setattr(api, "_check_redis", redis_skip)
    monkeypatch.setattr(api, "_check_runtime_flags", runtime_degraded)

    resp = _client().get("/readyz")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["runtime"]["status"] == "degraded"


def test_ready_alias_fails_on_postgres(monkeypatch):
    async def pg_fail(*_args, **_kwargs):
        return "fail", "connection refused"

    async def redis_ok(*_args, **_kwargs):
        return "ok", None

    def runtime_ok():
        return "ok", None

    monkeypatch.setattr(api, "_check_postgres", pg_fail)
    monkeypatch.setattr(api, "_check_redis", redis_ok)
    monkeypatch.setattr(api, "_check_runtime_flags", runtime_ok)

    resp = _client().get("/ready")
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "fail"
    assert payload["checks"]["postgres"]["detail"] == "connection refused"


def test_readyz_canary(monkeypatch):
    monkeypatch.setenv("CANARY", "1")
    reset_settings_cache()

    async def pg_ok(*_args, **_kwargs):
        return "ok", None

    async def redis_ok(*_args, **_kwargs):
        return "ok", None

    def runtime_ok():
        return "ok", None

    monkeypatch.setattr(api, "_check_postgres", pg_ok)
    monkeypatch.setattr(api, "_check_redis", redis_ok)
    monkeypatch.setattr(api, "_check_runtime_flags", runtime_ok)

    resp = _client().get("/readyz")
    reset_settings_cache()
    assert resp.status_code == 200
    assert resp.json().get("canary") is True
