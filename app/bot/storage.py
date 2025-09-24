"""
/**
 * @file: app/bot/storage.py
 * @description: SQLite helpers for user preferences, subscriptions and reports.
 * @dependencies: sqlite3, pathlib, config
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from config import settings

_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _ROOT / "database" / "schema.sql"


def ensure_schema(db_path: str | None = None) -> None:
    path = Path(db_path or settings.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(db_path or settings.DB_PATH)
    ensure_schema(str(path))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_preferences(user_id: int, *, db_path: str | None = None) -> dict[str, Any]:
    with _connect(db_path) as conn:
        cur = conn.execute("SELECT * FROM user_prefs WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return {"user_id": user_id, "tz": "UTC", "lang": "ru", "odds_format": "decimal"}
        return dict(row)


def upsert_user_preferences(
    user_id: int,
    *,
    tz: str | None = None,
    lang: str | None = None,
    odds_format: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    with _connect(db_path) as conn:
        existing = get_user_preferences(user_id, db_path=db_path)
        tz_value = tz or existing.get("tz", "UTC")
        lang_value = lang or existing.get("lang", "ru")
        odds_value = odds_format or existing.get("odds_format", "decimal")
        conn.execute(
            """
            INSERT INTO user_prefs (user_id, tz, lang, odds_format, created_at, updated_at)
            VALUES (?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                tz = excluded.tz,
                lang = excluded.lang,
                odds_format = excluded.odds_format,
                updated_at = DATETIME('now')
            """,
            (user_id, tz_value, lang_value, odds_value),
        )
        conn.commit()
    return get_user_preferences(user_id, db_path=db_path)


def upsert_subscription(
    user_id: int,
    *,
    send_at: str,
    tz: str,
    league: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, league, send_at, tz, created_at, updated_at)
            VALUES (?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                league = excluded.league,
                send_at = excluded.send_at,
                tz = excluded.tz,
                updated_at = DATETIME('now')
            """,
            (user_id, league, send_at, tz),
        )
        conn.commit()
        cur = conn.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    return dict(row) if row else {}


def list_subscriptions(*, db_path: str | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        cur = conn.execute("SELECT * FROM subscriptions ORDER BY user_id")
        return [dict(row) for row in cur.fetchall()]


def delete_subscription(user_id: int, *, db_path: str | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        conn.commit()


def record_report(
    report_id: str,
    *,
    match_id: int,
    path: str,
    db_path: str | None = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reports (report_id, match_id, path, created_at)
            VALUES (?, ?, ?, DATETIME('now'))
            ON CONFLICT(report_id) DO UPDATE SET path = excluded.path
            """,
            (report_id, match_id, path),
        )
        conn.commit()


def list_reports(limit: int = 10, *, db_path: str | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def iter_reports_for_match(match_id: int, *, db_path: str | None = None) -> Iterable[dict[str, Any]]:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM reports WHERE match_id = ? ORDER BY created_at DESC",
            (match_id,),
        )
        for row in cur:
            yield dict(row)


def get_value_alert(user_id: int, *, db_path: str | None = None) -> dict[str, object]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM value_alerts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "user_id": user_id,
                "enabled": False,
                "edge_threshold": 5.0,
                "league": None,
            }
        result = dict(row)
        result["enabled"] = bool(result.get("enabled", 0))
        return result


def upsert_value_alert(
    user_id: int,
    *,
    enabled: bool | None = None,
    edge_threshold: float | None = None,
    league: str | None = None,
    db_path: str | None = None,
) -> dict[str, object]:
    current = get_value_alert(user_id, db_path=db_path)
    enabled_val = int(enabled if enabled is not None else current.get("enabled", False))
    edge_val = float(edge_threshold if edge_threshold is not None else current.get("edge_threshold", 5.0))
    league_val = league if league is not None else current.get("league")
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO value_alerts(user_id, enabled, edge_threshold, league, created_at, updated_at)
            VALUES (?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                enabled = excluded.enabled,
                edge_threshold = excluded.edge_threshold,
                league = excluded.league,
                updated_at = DATETIME('now')
            """,
            (user_id, enabled_val, edge_val, league_val),
        )
        conn.commit()
    return get_value_alert(user_id, db_path=db_path)


def record_value_alert_sent(
    user_id: int,
    *,
    match_key: str,
    market: str,
    selection: str,
    edge_pct: float,
    db_path: str | None = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO value_alerts_sent(user_id, match_key, market, selection, edge_pct, sent_at)
            VALUES (?, ?, ?, ?, ?, DATETIME('now'))
            """,
            (user_id, match_key, market, selection, float(edge_pct)),
        )
        conn.commit()


def get_last_value_alert_sent(
    user_id: int,
    *,
    match_key: str,
    market: str,
    selection: str,
    db_path: str | None = None,
) -> dict[str, object] | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM value_alerts_sent
            WHERE user_id = ? AND match_key = ? AND market = ? AND selection = ?
            ORDER BY sent_at DESC LIMIT 1
            """,
            (user_id, match_key, market, selection),
        ).fetchone()
        return dict(row) if row else None


def list_recent_value_alerts(
    user_id: int,
    *,
    limit: int = 5,
    db_path: str | None = None,
) -> list[dict[str, object]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM value_alerts_sent
            WHERE user_id = ?
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (user_id, int(max(limit, 1))),
        ).fetchall()
        return [dict(row) for row in rows]


__all__ = [
    "ensure_schema",
    "get_user_preferences",
    "upsert_user_preferences",
    "upsert_subscription",
    "list_subscriptions",
    "delete_subscription",
    "record_report",
    "list_reports",
    "iter_reports_for_match",
    "get_value_alert",
    "upsert_value_alert",
    "record_value_alert_sent",
    "get_last_value_alert_sent",
    "list_recent_value_alerts",
]
