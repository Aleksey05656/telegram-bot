"""
@file: test_metrics_sentry.py
@description: Smoke tests for health and metrics endpoints
@dependencies: app.api
@created: 2025-09-10
"""

from fastapi.testclient import TestClient

from app import api
from app.config import reset_settings_cache


def test_health_aliases():
    client = TestClient(api.app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    alias = client.get("/health")
    assert alias.status_code == 200
    assert alias.json()["status"] == "ok"


def test_metrics_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_METRICS", raising=False)
    reset_settings_cache()
    client = TestClient(api.app)
    try:
        resp = client.get("/metrics")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "metrics disabled"}
    finally:
        reset_settings_cache()


def test_metrics_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_METRICS", "1")
    monkeypatch.setattr(api, "generate_latest", lambda *_args, **_kwargs: b"# HELP\n", raising=False)
    monkeypatch.setattr(api, "CONTENT_TYPE_LATEST", "text/plain; version=0.0.4", raising=False)
    reset_settings_cache()
    client = TestClient(api.app)
    try:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "# HELP" in resp.text
    finally:
        reset_settings_cache()
