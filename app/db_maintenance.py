"""
@file: db_maintenance.py
@description: SQLite maintenance utilities (PRAGMA, backups, vacuum).
@dependencies: sqlite3
@created: 2025-09-30
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

__all__ = ["apply_pragmas", "backup_sqlite", "vacuum_analyze"]


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply recommended SQLite PRAGMA settings on the given connection."""

    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA busy_timeout=5000;")
    conn.commit()


def backup_sqlite(db_path: str, backup_dir: str, keep: int = 10) -> str:
    """Create a timestamped SQLite backup and rotate old copies."""

    source = Path(db_path)
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    backup_root = Path(backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    destination = backup_root / f"bot-{ts}.sqlite3"
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        apply_pragmas(dst)
        src.backup(dst)
    files = sorted(backup_root.glob("bot-*.sqlite3"))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)
    return str(destination)


def vacuum_analyze(db_path: str) -> None:
    """Run VACUUM and ANALYZE on the given SQLite database."""

    with sqlite3.connect(db_path) as conn:
        apply_pragmas(conn)
        conn.execute("VACUUM;")
        conn.execute("ANALYZE;")
        conn.commit()
