"""
@file: tests/smoke/test_metrics_endpoint.py
@description: Smoke test for Prometheus /metrics endpoint
@dependencies: app.api
@created: 2025-09-15
"""

from fastapi.testclient import TestClient

from app.api import app
from app.config import reset_settings_cache


def test_metrics_endpoint_returns_text_plain(monkeypatch):
    monkeypatch.setenv("ENABLE_METRICS", "1")
    reset_settings_cache()
    client = TestClient(app)
    try:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "# HELP" in resp.text
    finally:
        reset_settings_cache()
