"""
@file: tests/smoke/test_cli_retrain.py
@description: Smoke test for CLI retrain orchestration commands.
@dependencies: scripts/cli.py, workers.runtime_scheduler, app.main
@created: 2025-09-16
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import workers.runtime_scheduler as runtime_scheduler


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        ["python", "scripts/cli.py", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_retrain_run_and_schedule(monkeypatch, tmp_path):
    runtime_scheduler.clear_jobs()
    monkeypatch.delenv("RETRAIN_CRON", raising=False)

    repo_root = Path(__file__).resolve().parents[2]
    registry_root = tmp_path / "artifacts"
    reports_root = tmp_path / "reports"
    logs_root = tmp_path / "logs"
    db_path = tmp_path / "bot.sqlite3"
    monkeypatch.setenv("MODEL_REGISTRY_PATH", str(registry_root))
    monkeypatch.setenv("REPORTS_DIR", str(reports_root))
    monkeypatch.setenv("LOG_DIR", str(logs_root))
    monkeypatch.setenv("DB_PATH", str(db_path))

    artifacts_dir = registry_root / "default"
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
    metrics_report = reports_root / "metrics" / "MODIFIERS_default.md"
    if metrics_report.exists():
        metrics_report.unlink()

    summary_path = reports_root / "RUN_SUMMARY.md"
    summary_before = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""

    result = _run_cli("retrain", "run", "--season-id", "default", "--with-modifiers")
    assert "season=default" in result.stdout

    assert (artifacts_dir / "glm_home.pkl").exists()
    assert (artifacts_dir / "glm_away.pkl").exists()
    assert (artifacts_dir / "model_info.json").exists()

    assert metrics_report.exists()
    metrics_text = metrics_report.read_text(encoding="utf-8")
    assert "| logloss |" in metrics_text

    summary_after = summary_path.read_text(encoding="utf-8")
    assert summary_after.count("## CLI retrain") == summary_before.count("## CLI retrain") + 1
    assert "- Season: default" in summary_after

    if "app.main" in sys.modules:
        importlib.reload(sys.modules["app.main"])
    else:
        import app.main  # noqa: F401

    from app.main import app  # type: ignore

    client = TestClient(app)
    payload_before = client.get("/__smoke__/retrain").json()
    total_before = payload_before["jobs_registered_total"]

    schedule_result = _run_cli("retrain", "schedule")
    assert "scheduled" in schedule_result.stdout

    payload_after = client.get("/__smoke__/retrain").json()
    assert payload_after["jobs_registered_total"] == total_before + 1
