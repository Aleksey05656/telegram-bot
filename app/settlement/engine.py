"""
/**
 * @file: app/settlement/engine.py
 * @description: Settlement engine that resolves picks using SportMonks final scores and updates ROI/CLV.
 * @dependencies: dataclasses, sqlite3, datetime, typing, app.value_clv, app.metrics
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from app.metrics import clv_mean_pct, picks_settled_total, portfolio_roi_rolling
from app.value_clv import calculate_clv
from config import settings


def _from_iso(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class FixtureResult:
    match_key: str
    home_score: int
    away_score: int
    status: str = "finished"


class ResultsProvider(Protocol):
    def fetch(self, match_keys: Sequence[str]) -> Mapping[str, FixtureResult]:
        """Return final results for requested match keys."""


@dataclass(slots=True)
class SettlementEngine:
    """Settle value picks and compute ROI metrics."""

    results_provider: ResultsProvider
    db_path: str = settings.DB_PATH
    poll_min: int = int(getattr(settings, "SETTLEMENT_POLL_MIN", 10))
    max_lag_hours: int = int(getattr(settings, "SETTLEMENT_MAX_LAG_HOURS", 24))
    rolling_days: int = int(getattr(settings, "PORTFOLIO_ROLLING_DAYS", 60))

    def __post_init__(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def settle(self) -> int:
        picks = self._load_unsettled_picks()
        if not picks:
            self._update_portfolio_metrics()
            return 0
        match_keys = sorted({pick["match_key"] for pick in picks})
        results = self.results_provider.fetch(match_keys)
        settled = 0
        now = datetime.now(UTC)
        with self._connect() as conn:
            for row in picks:
                match_key = row["match_key"]
                result = results.get(match_key)
                if not result or result.status.lower() != "finished":
                    continue
                outcome = self._determine_outcome(
                    market=row["market"],
                    selection=row["selection"],
                    home_score=result.home_score,
                    away_score=result.away_score,
                )
                if outcome is None:
                    continue
                roi_value = self._compute_roi(row["price_taken"], outcome)
                clv_value = row["clv_pct"]
                if clv_value is None and row["closing_price"] is not None:
                    try:
                        clv_value = calculate_clv(float(row["price_taken"]), float(row["closing_price"]))
                    except ZeroDivisionError:
                        clv_value = 0.0
                conn.execute(
                    """
                    UPDATE picks_ledger
                       SET outcome = ?,
                           roi = ?,
                           clv_pct = COALESCE(?, clv_pct),
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        outcome,
                        roi_value,
                        clv_value,
                        _to_iso(now),
                        int(row["id"]),
                    ),
                )
                picks_settled_total.labels(outcome=outcome).inc()
                settled += 1
            conn.commit()
        self._update_portfolio_metrics()
        return settled

    def _load_unsettled_picks(self) -> list[sqlite3.Row]:
        cutoff = datetime.now(UTC) - timedelta(minutes=max(self.poll_min, 1))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, match_key, market, selection, price_taken,
                       provider_price_decimal, consensus_price_decimal,
                       kickoff_utc, clv_pct, closing_price, outcome
                  FROM picks_ledger
                 WHERE outcome IS NULL
                """,
            ).fetchall()
        eligible: list[sqlite3.Row] = []
        for row in rows:
            kickoff_raw = row["kickoff_utc"]
            try:
                kickoff = _from_iso(str(kickoff_raw))
            except Exception:
                continue
            if kickoff > cutoff:
                continue
            eligible.append(row)
        return eligible

    @staticmethod
    def _compute_roi(price_taken: float, outcome: str) -> float:
        price = float(price_taken)
        if outcome == "win":
            return (price - 1.0) * 100.0
        if outcome == "lose":
            return -100.0
        return 0.0

    @staticmethod
    def _determine_outcome(
        *,
        market: str,
        selection: str,
        home_score: int,
        away_score: int,
    ) -> str | None:
        market_key = market.upper()
        selection_key = selection.upper()
        if market_key == "1X2":
            if home_score > away_score:
                return "win" if selection_key == "HOME" else "lose"
            if home_score < away_score:
                return "win" if selection_key == "AWAY" else "lose"
            return "win" if selection_key == "DRAW" else "lose"
        if market_key.startswith("OU_"):
            line_part = market_key.split("_", 1)[1]
            try:
                handicap = float(line_part.replace("_", "."))
            except ValueError:
                return None
            total_goals = home_score + away_score
            if selection_key == "OVER":
                if total_goals > handicap:
                    return "win"
                if total_goals == handicap:
                    return "push"
                return "lose"
            if selection_key == "UNDER":
                if total_goals < handicap:
                    return "win"
                if total_goals == handicap:
                    return "push"
                return "lose"
        if market_key == "BTTS":
            both_scored = home_score > 0 and away_score > 0
            if selection_key == "YES":
                return "win" if both_scored else "lose"
            if selection_key == "NO":
                return "lose" if both_scored else "win"
        return None

    def _update_portfolio_metrics(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=max(self.rolling_days, 1))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT roi, clv_pct
                  FROM picks_ledger
                 WHERE outcome IS NOT NULL
                   AND created_at >= ?
                """,
                (_to_iso(cutoff),),
            ).fetchall()
        roi_values = [float(row["roi"]) for row in rows if row["roi"] is not None]
        clv_values = [float(row["clv_pct"]) for row in rows if row["clv_pct"] is not None]
        avg_roi = sum(roi_values) / len(roi_values) if roi_values else 0.0
        avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0
        portfolio_roi_rolling.labels(window_days=str(self.rolling_days)).set(avg_roi)
        clv_mean_pct.set(avg_clv)


__all__ = ["FixtureResult", "ResultsProvider", "SettlementEngine"]

