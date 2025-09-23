"""
/**
 * @file: tests/diagtools/test_scheduler.py
 * @description: Tests for diagnostics scheduler orchestration and runtime budget.
 * @dependencies: diagtools.scheduler
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import json
from typing import Iterable

from config import settings
from diagtools import scheduler


class FakeTime:
    def __init__(self) -> None:
        self.current = 0.0

    def advance(self, delta: float) -> None:
        self.current += delta

    def __call__(self) -> float:
        return self.current


def test_run_suite_respects_time_budget(monkeypatch, tmp_path) -> None:
    reports_root = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(settings, "REPORTS_DIR", str(reports_root))
    monkeypatch.setattr(settings, "LOG_DIR", str(log_dir))
    monkeypatch.setattr(settings, "DIAG_MAX_RUNTIME_MIN", 0.001)
    monkeypatch.setattr(settings, "ALERTS_ENABLED", False)
    fake_time = FakeTime()

    def runner(
        name: str,
        command: list[str],
        env: dict[str, str],
        log_path,
        secrets: Iterable[str],
    ) -> scheduler.CommandExecution:
        fake_time.advance(10.0)
        diag_dir = reports_root / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        if name == "diag-run":
            payload = {"statuses": {"Data Quality": {"status": "⚠️", "note": "warn"}}}
            (diag_dir / "diagnostics_report.json").write_text(json.dumps(payload), encoding="utf-8")
            site_dir = diag_dir / "site"
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        return scheduler.CommandExecution(
            name=name,
            command=command,
            returncode=0,
            duration_sec=1.0,
            stdout="",
            stderr="",
        )

    result = scheduler.run_suite(
        trigger="manual",
        reports_dir=str(reports_root),
        command_runner=runner,
        time_provider=fake_time,
    )

    assert result.commands[0].name == "diag-run"
    assert len(result.commands) == 1
    assert result.statuses["Data Quality"]["status"] == "⚠️"
    assert result.html_path is not None and result.html_path.exists()
    assert not result.alerts_sent
