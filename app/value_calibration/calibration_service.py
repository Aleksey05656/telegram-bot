"""
/**
 * @file: app/value_calibration/calibration_service.py
 * @description: SQLite-backed service providing calibrated thresholds per league/market.
 * @dependencies: sqlite3, datetime, pathlib, app.bot.storage
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from app.bot.storage import ensure_schema
from config import settings

_DB_PATH = Path(settings.DB_PATH)


@dataclass(slots=True)
class CalibrationRecord:
    """Persisted calibration thresholds."""

    league: str
    market: str
    tau_edge: float
    gamma_conf: float
    samples: int
    metric: float
    updated_at: datetime


class CalibrationService:
    """High-level API to read/write calibration thresholds with sensible fallbacks."""

    def __init__(
        self,
        *,
        default_edge_pct: float,
        default_confidence: float,
        db_path: str | None = None,
    ) -> None:
        self._default_edge = float(default_edge_pct)
        self._default_conf = float(default_confidence)
        self._db_path = Path(db_path) if db_path else _DB_PATH
        ensure_schema(str(self._db_path))

    def thresholds_for(self, league: str | None, market: str) -> CalibrationRecord:
        league_key = (league or "").strip()
        market_key = market.strip().upper()
        query = (
            "SELECT league, market, tau_edge, gamma_conf, samples, metric, updated_at "
            "FROM value_calibration WHERE league = ? AND market = ?"
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, (league_key, market_key)).fetchone()
        if not row:
            return CalibrationRecord(
                league=league_key,
                market=market_key,
                tau_edge=self._default_edge,
                gamma_conf=self._default_conf,
                samples=0,
                metric=0.0,
                updated_at=datetime.now(UTC),
            )
        updated_at = _coerce_datetime(row["updated_at"])
        return CalibrationRecord(
            league=str(row["league"]),
            market=str(row["market"]),
            tau_edge=float(row["tau_edge"]),
            gamma_conf=float(row["gamma_conf"]),
            samples=int(row["samples"]),
            metric=float(row["metric"]),
            updated_at=updated_at,
        )

    def bulk_upsert(self, records: Sequence[CalibrationRecord]) -> None:
        if not records:
            return
        payload = [
            (
                record.league,
                record.market,
                record.tau_edge,
                record.gamma_conf,
                record.samples,
                record.metric,
                record.updated_at.astimezone(UTC).isoformat(timespec="seconds"),
            )
            for record in records
        ]
        statement = (
            "INSERT INTO value_calibration(league, market, tau_edge, gamma_conf, samples, metric, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(league, market) DO UPDATE SET "
            "tau_edge = excluded.tau_edge, "
            "gamma_conf = excluded.gamma_conf, "
            "samples = excluded.samples, "
            "metric = excluded.metric, "
            "updated_at = excluded.updated_at"
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executemany(statement, payload)
            conn.commit()

    def list_all(self) -> list[CalibrationRecord]:
        query = (
            "SELECT league, market, tau_edge, gamma_conf, samples, metric, updated_at "
            "FROM value_calibration ORDER BY league, market"
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
        results: list[CalibrationRecord] = []
        for row in rows:
            results.append(
                CalibrationRecord(
                    league=str(row["league"]),
                    market=str(row["market"]),
                    tau_edge=float(row["tau_edge"]),
                    gamma_conf=float(row["gamma_conf"]),
                    samples=int(row["samples"]),
                    metric=float(row["metric"]),
                    updated_at=_coerce_datetime(row["updated_at"]),
                )
            )
        return results


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(UTC)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)


__all__ = ["CalibrationRecord", "CalibrationService"]
