"""
@file: app/lines/storage.py
@description: Persistence helpers for odds snapshots stored in SQLite.
@dependencies: sqlite3, json, app.lines.providers.base
@created: 2025-09-24
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from config import settings

from app.lines.providers.base import OddsSnapshot


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class OddsSQLiteStore:
    """Persist odds snapshots in SQLite keeping the latest entry per selection."""

    db_path: str = settings.DB_PATH

    def __post_init__(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS odds_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    pulled_at_utc TEXT NOT NULL,
                    match_key TEXT NOT NULL,
                    league TEXT NULL,
                    kickoff_utc TEXT NOT NULL,
                    market TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    price_decimal REAL NOT NULL,
                    extra_json TEXT NULL,
                    UNIQUE(provider, match_key, market, selection)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS odds_match
                ON odds_snapshots(match_key, market, selection)
                """
            )
            conn.commit()

    def upsert(self, snapshot: OddsSnapshot) -> None:
        self.upsert_many([snapshot])

    def upsert_many(self, snapshots: Iterable[OddsSnapshot]) -> None:
        payload = [
            (
                item.provider,
                _to_iso(item.pulled_at),
                item.match_key,
                item.league,
                _to_iso(item.kickoff_utc),
                item.market,
                item.selection,
                float(item.price_decimal),
                json.dumps(item.extra or {}),
            )
            for item in snapshots
        ]
        if not payload:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO odds_snapshots(
                    provider, pulled_at_utc, match_key, league, kickoff_utc,
                    market, selection, price_decimal, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, match_key, market, selection) DO UPDATE SET
                    pulled_at_utc=excluded.pulled_at_utc,
                    league=excluded.league,
                    kickoff_utc=excluded.kickoff_utc,
                    price_decimal=excluded.price_decimal,
                    extra_json=excluded.extra_json
                """,
                payload,
            )
            conn.commit()

    def fetch_latest(
        self,
        *,
        leagues: Sequence[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        query = [
            "SELECT provider, pulled_at_utc, match_key, league, kickoff_utc,",
            "       market, selection, price_decimal, extra_json",
            "  FROM odds_snapshots",
        ]
        params: list[object] = []
        if leagues:
            placeholders = ",".join("?" for _ in leagues)
            query.append(f" WHERE league IN ({placeholders})")
            params.extend(leagues)
        query.append(" ORDER BY pulled_at_utc DESC LIMIT ?")
        params.append(limit)
        sql = "".join(query)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            payload = dict(row)
            extra = payload.get("extra_json")
            payload["extra_json"] = json.loads(extra) if isinstance(extra, str) else {}
            result.append(payload)
        return result


__all__ = ["OddsSQLiteStore"]
