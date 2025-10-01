"""
@file: test_start_stats.py
@description: Coverage for start menu statistics rendering.
@dependencies: sqlite3, tgbotapp.handlers.start
@created: 2025-10-21
"""
from __future__ import annotations

import sqlite3

import pytest

from config import settings
from tgbotapp.handlers import start as start_handler


@pytest.mark.asyncio
async def test_stats_message_reports_counts(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "stats.sqlite3"
    monkeypatch.setattr(settings, "DB_PATH", str(db_path))
    monkeypatch.setattr(settings, "APP_VERSION", "9.9.9")
    monkeypatch.setattr(settings, "GIT_SHA", "deadbeef")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE predictions (ts TEXT)")
    conn.execute("INSERT INTO predictions(ts) VALUES (?)", ("2025-10-20T10:00:00",))
    conn.execute("CREATE TABLE reports (created_at TEXT)")
    conn.execute("INSERT INTO reports(created_at) VALUES (?)", ("2025-10-20 09:00:00",))
    conn.execute(
        "CREATE TABLE user_prefs (user_id INTEGER PRIMARY KEY, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO user_prefs(user_id, updated_at) VALUES (1, '2025-10-19 08:00:00')"
    )
    conn.execute(
        "CREATE TABLE subscriptions (user_id INTEGER PRIMARY KEY, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO subscriptions(user_id, updated_at) VALUES (1, '2025-10-19 08:30:00')"
    )
    conn.commit()
    conn.close()

    text = await start_handler._build_stats_message()
    assert "Предсказаний сохранено: 1" in text
    assert "Пользовательских профилей: 1" in text
    assert "Активных подписок: 1" in text
    assert "Версия: 9.9.9 (deadbeef)" in text
    assert "DEGRADED" not in text


@pytest.mark.asyncio
async def test_stats_message_marks_degraded(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "missing.sqlite3"
    monkeypatch.setattr(settings, "DB_PATH", str(db_path))

    text = await start_handler._build_stats_message()
    assert "DEGRADED" in text
