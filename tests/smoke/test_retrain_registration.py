"""
@file: tests/smoke/test_retrain_registration.py
@description: Smoke tests for retrain scheduler registration feature flag.
@dependencies: app.main, workers.runtime_scheduler
@created: 2025-09-12
"""

import importlib
import os
import sys

from fastapi.testclient import TestClient


def test_retrain_registration_feature_flag(monkeypatch):
    # make sure runtime registry is empty
    import workers.runtime_scheduler as rs

    rs.clear_jobs()

    # enable feature flag via env
    monkeypatch.setenv("RETRAIN_CRON", "*/15 * * * *")

    # reload app.main to re-run init wiring under new env
    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])
    else:
        import app.main  # noqa: F401

    from app.main import app  # type: ignore

    c = TestClient(app)
    r = c.get("/__smoke__/retrain")
    assert r.status_code == 200
    payload = r.json()
    assert payload["enabled"] is True
    assert payload["count"] >= 1
    assert "*/15 * * * *" in payload["crons"]
    assert payload["jobs_registered_total"] >= payload["count"]


def test_retrain_registration_disabled_by_default(monkeypatch):
    import workers.runtime_scheduler as rs

    rs.clear_jobs()
    # disable via empty / explicit off
    monkeypatch.delenv("RETRAIN_CRON", raising=False)

    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])
    else:
        import app.main  # noqa: F401

    from app.main import app  # type: ignore

    c = TestClient(app)
    r = c.get("/__smoke__/retrain")
    payload = r.json()
    assert payload["enabled"] in (False, None)
    assert payload["count"] == 0
    assert payload["jobs_registered_total"] >= 0
