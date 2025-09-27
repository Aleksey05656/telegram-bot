"""
@file: tests/smoke/test_endpoints.py
@description: Smoke coverage for basic service endpoints
@dependencies: app.api
@created: 2025-09-15
"""

from fastapi.testclient import TestClient

from app.api import app
from app.config import reset_settings_cache


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert client.get("/health").status_code == 200


def test_metrics_ok(monkeypatch):
    monkeypatch.setenv("ENABLE_METRICS", "1")
    reset_settings_cache()
    client = TestClient(app)
    try:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
    finally:
        reset_settings_cache()


def test_sentry_smoke():
    client = TestClient(app)
    r = client.get("/__smoke__/sentry")
    assert r.status_code == 200


def test_retrain_smoke():
    client = TestClient(app)
    r = client.get("/__smoke__/retrain")
    assert r.status_code == 200
    assert "jobs_registered_total" in r.json()


def test_warmup_smoke():
    client = TestClient(app)
    response = client.get("/__smoke__/warmup")
    assert response.status_code == 200
    payload = response.json()
    assert "warmed" in payload
    assert "took_ms" in payload
