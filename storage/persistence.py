"""
@file: persistence.py
@description: Storage layer for simulation predictions with SQLite fallback.
@dependencies: sqlite3, json, os
@created: 2025-09-15
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


DEFAULT_DB_PATH = os.getenv("DB_PATH", "/data/bot.sqlite3")


class PredictionsStore(Protocol):
    """Interface for persisting market probabilities."""

    def write(self, match_id: str, market: str, selection: str, prob: float, meta: dict) -> None:
        ...

    def bulk_write(self, records: Iterable[tuple[str, str, str, float, dict]]) -> None:
        ...


@dataclass
class SQLitePredictionsStore:
    db_path: str = DEFAULT_DB_PATH

    def __post_init__(self) -> None:
        path = Path(self.db_path)
        if not path.is_absolute():
            base_root = Path(os.getenv("DATA_ROOT", "/data"))
            path = base_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions(
                match_id TEXT,
                market TEXT,
                selection TEXT,
                prob REAL,
                ts TEXT,
                season TEXT,
                extra TEXT,
                PRIMARY KEY(match_id, market, selection, ts)
            )
            """
        )
        conn.commit()
        conn.close()

    def write(self, match_id: str, market: str, selection: str, prob: float, meta: dict) -> None:
        self.bulk_write([(match_id, market, selection, prob, meta)])

    def bulk_write(self, records: Iterable[tuple[str, str, str, float, dict]]) -> None:
        conn = self._connect()
        cur = conn.cursor()
        data = []
        for match_id, market, selection, prob, meta in records:
            data.append(
                (
                    match_id,
                    market,
                    selection,
                    prob,
                    meta.get("ts"),
                    meta.get("season"),
                    json.dumps(meta.get("extra", {})),
                )
            )
        cur.executemany(
            """
            INSERT INTO predictions(match_id, market, selection, prob, ts, season, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id, market, selection, ts) DO UPDATE SET
                prob=excluded.prob,
                season=excluded.season,
                extra=excluded.extra
            """,
            data,
        )
        conn.commit()
        conn.close()
