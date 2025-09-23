"""
/**
 * @file: tests/bot/test_chatops_diag.py
 * @description: Tests for admin Chat-Ops diagnostics command handlers.
 * @dependencies: app.bot.routers.commands, diagtools.scheduler
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.bot.routers import commands as commands_module
from config import settings
from diagtools import reports_html, scheduler


class DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class DummyMessage:
    def __init__(self, user_id: int) -> None:
        self.from_user = DummyUser(user_id)
        self.answers: list[str] = []
        self.documents: list[tuple[object, str | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:  # pragma: no cover - async helper
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None) -> None:  # pragma: no cover
        self.documents.append((document, caption))


@pytest.mark.asyncio
async def test_diag_last_history(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands_module, "_ADMIN_IDS", {42})
    entry = reports_html.HistoryEntry(
        timestamp="2024-01-01T00:00:00Z",
        trigger="cron",
        status="OK",
        duration_sec=12.3,
        warn_sections=[],
        fail_sections=[],
        html_path="/tmp/index.html",
        report_path="/tmp/diagnostics_report.json",
    )
    monkeypatch.setattr(scheduler, "load_history", lambda limit=1: [entry])
    message = DummyMessage(42)
    await commands_module.handle_diag_admin(message, SimpleNamespace(args="last"))
    assert any("Последний запуск" in line for line in message.answers)


@pytest.mark.asyncio
async def test_diag_manual_run(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands_module, "_ADMIN_IDS", {7})
    result = scheduler.DiagnosticsRunResult(
        trigger="manual",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        statuses={"Data": {"status": "✅", "note": "ok"}},
        commands=[scheduler.CommandExecution("diag-run", [], 0, 1.0, "", "")],
        log_path=tmp_path / "diag.log",
        html_path=tmp_path / "index.html",
        alerts_sent=False,
    )
    result.html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(scheduler, "run_suite", lambda trigger="manual": result)
    message = DummyMessage(7)
    await commands_module.handle_diag_admin(message, SimpleNamespace(args=""))
    assert any("Готово" in line for line in message.answers)


@pytest.mark.asyncio
async def test_diag_link(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands_module, "_ADMIN_IDS", {77})
    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))
    site_dir = Path(settings.REPORTS_DIR) / "diagnostics" / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    index = site_dir / "index.html"
    index.write_text("<html></html>", encoding="utf-8")
    message = DummyMessage(77)
    await commands_module.handle_diag_admin(message, SimpleNamespace(args="link"))
    assert message.documents and "Diagnostics" in (message.documents[0][1] or "")
