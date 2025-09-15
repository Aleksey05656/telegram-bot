"""
@file: tests/smoke/test_metrics_endpoint.py
@description: Smoke test for Prometheus /metrics endpoint
@dependencies: app.main
@created: 2025-09-15
"""

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_returns_text_plain():
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "# HELP" in resp.text
