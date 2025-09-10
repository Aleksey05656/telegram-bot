"""
@file: test_metrics_sentry.py
@description: Smoke tests for health endpoint and metrics availability
@dependencies: app.main
@created: 2025-09-10
"""

from fastapi.testclient import TestClient
from app.main import app


def test_health_ok():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exists():
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code in (200, 404)  # зависит от settings
    if r.status_code == 200:
        assert "requests_total" in r.text
