"""
@file: app/lines/storage.py
@description: Persistence helpers for odds snapshots stored in SQLite with history queries.
@dependencies: sqlite3, json, datetime, app.lines.providers.base
@created: 2025-09-24
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from config import settings

from app.lines.providers.base import OddsSnapshot


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _from_iso(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True, frozen=True)
class LineHistoryPoint:
    provider: str
    pulled_at: datetime
    price_decimal: float


@dataclass(slots=True)
class OddsSQLiteStore:
    """Persist odds snapshots in SQLite and expose history helpers."""

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
                    UNIQUE(provider, match_key, market, selection, pulled_at_utc)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS odds_match
                ON odds_snapshots(match_key, market, selection)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS odds_match_time
                ON odds_snapshots(match_key, market, selection, pulled_at_utc)
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
                ON CONFLICT(provider, match_key, market, selection, pulled_at_utc) DO UPDATE SET
                    league=excluded.league,
                    kickoff_utc=excluded.kickoff_utc,
                    price_decimal=excluded.price_decimal,
                    extra_json=excluded.extra_json
                """,
                payload,
            )
            conn.commit()

    def purge_older_than(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_iso = _to_iso(cutoff)
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM odds_snapshots WHERE pulled_at_utc < ?",
                (cutoff_iso,),
            )
            conn.commit()
            return int(cur.rowcount or 0)

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

    def history(
        self,
        *,
        match_key: str,
        market: str,
        selection: str,
        limit: int = 200,
    ) -> list[LineHistoryPoint]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider, pulled_at_utc, price_decimal
                  FROM odds_snapshots
                 WHERE match_key = ? AND market = ? AND selection = ?
                 ORDER BY pulled_at_utc ASC
                 LIMIT ?
                """,
                (match_key, market, selection, int(max(limit, 1))),
            ).fetchall()
        history = [
            LineHistoryPoint(
                provider=str(row["provider"]),
                pulled_at=_from_iso(str(row["pulled_at_utc"])),
                price_decimal=float(row["price_decimal"]),
            )
            for row in rows
        ]
        return history

    def latest_quotes(
        self,
        *,
        match_key: str,
        market: str,
        selection: str,
    ) -> list[OddsSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider, pulled_at_utc, match_key, league, kickoff_utc,
                       market, selection, price_decimal, extra_json
                  FROM odds_snapshots
                 WHERE match_key = ? AND market = ? AND selection = ?
                 ORDER BY pulled_at_utc DESC
                """,
                (match_key, market, selection),
            ).fetchall()
        latest: list[OddsSnapshot] = []
        seen: set[str] = set()
        for row in rows:
            provider = str(row["provider"])
            if provider in seen:
                continue
            seen.add(provider)
            extra_raw = row["extra_json"]
            extra = json.loads(extra_raw) if isinstance(extra_raw, str) else {}
            latest.append(
                OddsSnapshot(
                    provider=provider,
                    pulled_at=_from_iso(str(row["pulled_at_utc"])),
                    match_key=str(row["match_key"]),
                    league=str(row["league"]) if row["league"] is not None else None,
                    kickoff_utc=_from_iso(str(row["kickoff_utc"])),
                    market=str(row["market"]),
                    selection=str(row["selection"]),
                    price_decimal=float(row["price_decimal"]),
                    extra=extra,
                )
            )
        return latest


__all__ = ["LineHistoryPoint", "OddsSQLiteStore"]
