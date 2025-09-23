"""
@file: test_db_maintenance.py
@description: Tests for SQLite maintenance utilities.
@dependencies: app.db_maintenance
@created: 2025-09-30
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db_maintenance import apply_pragmas, backup_sqlite, vacuum_analyze


def test_apply_pragmas_configures_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        apply_pragmas(conn)
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        temp_store = conn.execute("PRAGMA temp_store;").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
    finally:
        conn.close()
    assert journal_mode.lower() == "wal"
    assert synchronous in {1, "1"}
    assert foreign_keys == 1
    assert temp_store in {2, "2"}
    assert busy_timeout == 5000


def test_backup_sqlite_creates_and_rotates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "main.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT);")
    conn.execute("INSERT INTO t(value) VALUES ('x')")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"

    class _Clock:
        def __init__(self) -> None:
            self._counter = 0

        def utcnow(self):  # type: ignore[override]
            self._counter += 1
            return _FixedTime(self._counter)

    class _FixedTime:
        def __init__(self, counter: int) -> None:
            self.counter = counter

        def strftime(self, fmt: str) -> str:
            return f"20240101-0000{self.counter:02d}"

    monkeypatch.setattr("app.db_maintenance.datetime", _Clock())

    created = [
        backup_sqlite(str(db_path), str(backup_dir), keep=5)
        for _ in range(7)
    ]
    assert Path(created[-1]).exists()
    existing = sorted(backup_dir.glob("bot-*.sqlite3"))
    assert len(existing) == 5


def test_vacuum_analyze_runs_without_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "vacuum.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT);")
    conn.executemany("INSERT INTO t(value) VALUES (?)", [(str(i),) for i in range(10)])
    conn.commit()
    conn.close()

    vacuum_analyze(str(db_path))
    # Ensure database still readable after maintenance
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM t;").fetchone()[0]
    finally:
        conn.close()
    assert count == 10
