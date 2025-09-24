"""
/**
 * @file: app/value_clv.py
 * @description: Closing line value calculations and picks ledger persistence helpers.
 * @dependencies: sqlite3, dataclasses, app.lines.aggregator, app.value_detector
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from app.lines.aggregator import ConsensusMeta
from config import settings

if TYPE_CHECKING:
    from app.value_detector import ValuePick


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

def calculate_clv(price_taken: float, closing_price: float) -> float:
    if price_taken <= 0 or closing_price <= 0:
        return 0.0
    return (price_taken / closing_price - 1.0) * 100.0


@dataclass(slots=True)
class PicksLedgerStore:
    db_path: str = settings.DB_PATH

    def __post_init__(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_pick(
        self,
        user_id: int,
        pick: ValuePick,
        consensus: ConsensusMeta,
        *,
        best_price: dict[str, object] | None = None,
    ) -> None:
        provider_price = (
            float(best_price.get("price_decimal"))
            if isinstance(best_price, dict) and best_price.get("price_decimal") is not None
            else float(pick.market_price)
        )
        consensus_price_decimal = float(consensus.price_decimal)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO picks_ledger(
                    user_id, match_key, market, selection, stake, price_taken,
                    provider_price_decimal,
                    model_probability, market_probability, edge_pct, confidence,
                    pulled_at_utc, kickoff_utc, consensus_price, consensus_price_decimal, consensus_method,
                    consensus_provider_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
                ON CONFLICT(user_id, match_key, market, selection, pulled_at_utc) DO UPDATE SET
                    price_taken=excluded.price_taken,
                    provider_price_decimal=excluded.provider_price_decimal,
                    model_probability=excluded.model_probability,
                    market_probability=excluded.market_probability,
                    edge_pct=excluded.edge_pct,
                    confidence=excluded.confidence,
                    consensus_price=excluded.consensus_price,
                    consensus_price_decimal=excluded.consensus_price_decimal,
                    consensus_method=excluded.consensus_method,
                    consensus_provider_count=excluded.consensus_provider_count,
                    updated_at=DATETIME('now')
                """,
                (
                    int(user_id),
                    pick.match_key,
                    pick.market,
                    pick.selection,
                    1.0,
                    provider_price,
                    provider_price,
                    float(pick.model_probability),
                    float(pick.market_probability),
                    float(pick.edge_pct),
                    float(pick.confidence),
                    _to_iso(pick.pulled_at),
                    _to_iso(pick.kickoff_utc),
                    float(consensus.price_decimal),
                    consensus_price_decimal,
                    consensus.method,
                    int(consensus.provider_count),
                ),
            )
            conn.commit()

    def record_closing_line(self, consensus: ConsensusMeta) -> None:
        if consensus.closing_price is None or consensus.closing_pulled_at is None:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO closing_lines(
                    match_key, market, selection, consensus_price, consensus_probability,
                    provider_count, method, pulled_at_utc, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now'))
                ON CONFLICT(match_key, market, selection) DO UPDATE SET
                    consensus_price=excluded.consensus_price,
                    consensus_probability=excluded.consensus_probability,
                    provider_count=excluded.provider_count,
                    method=excluded.method,
                    pulled_at_utc=excluded.pulled_at_utc,
                    updated_at=DATETIME('now')
                """,
                (
                    consensus.match_key,
                    consensus.market,
                    consensus.selection,
                    float(consensus.closing_price),
                    float(consensus.probability),
                    int(consensus.provider_count),
                    consensus.method,
                    _to_iso(consensus.closing_pulled_at),
                ),
            )
            conn.commit()

    def apply_closing_to_picks(self, consensus: ConsensusMeta) -> None:
        if consensus.closing_price is None or consensus.closing_pulled_at is None:
            return
        closing_price = consensus.closing_price
        closing_time = consensus.closing_pulled_at
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, price_taken
                  FROM picks_ledger
                 WHERE match_key = ? AND market = ? AND selection = ?
                """,
                (consensus.match_key, consensus.market, consensus.selection),
            ).fetchall()
            for row in rows:
                clv_pct = calculate_clv(float(row["price_taken"]), float(closing_price))
                conn.execute(
                    """
                    UPDATE picks_ledger
                       SET closing_price = ?,
                           closing_pulled_at = ?,
                           closing_method = ?,
                           clv_pct = ?,
                           updated_at = DATETIME('now')
                     WHERE id = ?
                    """,
                    (
                        float(closing_price),
                        _to_iso(closing_time),
                        consensus.method,
                        clv_pct,
                        int(row["id"]),
                    ),
                )
            conn.commit()

    def list_user_picks(
        self,
        user_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM picks_ledger
                 WHERE user_id = ?
                 ORDER BY created_at DESC
                 LIMIT ? OFFSET ?
                """,
                (int(user_id), int(max(limit, 1)), int(max(offset, 0))),
            ).fetchall()
        return [dict(row) for row in rows]

    def user_summary(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 5,
    ) -> dict[str, object]:
        page_size = max(page_size, 1)
        page = max(page, 1)
        offset = (page - 1) * page_size
        now = datetime.now(UTC)
        rolling_cutoff = now - timedelta(days=int(getattr(settings, "PORTFOLIO_ROLLING_DAYS", 60)))
        with self._connect() as conn:
            totals = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       AVG(clv_pct) AS avg_clv,
                       SUM(CASE WHEN clv_pct IS NOT NULL THEN 1 ELSE 0 END) AS clv_count,
                       SUM(CASE WHEN clv_pct IS NOT NULL AND clv_pct >= 0 THEN 1 ELSE 0 END) AS clv_positive,
                       AVG(edge_pct) AS avg_edge
                  FROM picks_ledger
                 WHERE user_id = ?
                """,
                (int(user_id),),
            ).fetchone()
            roi_row = conn.execute(
                """
                SELECT AVG(roi) AS avg_roi
                  FROM picks_ledger
                 WHERE user_id = ?
                   AND outcome IS NOT NULL
                   AND created_at >= ?
                """,
                (int(user_id), _to_iso(rolling_cutoff)),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT *
                  FROM picks_ledger
                 WHERE user_id = ?
                 ORDER BY created_at DESC
                 LIMIT ? OFFSET ?
                """,
                (int(user_id), int(page_size), int(offset)),
            ).fetchall()
        total = int(totals["total"] or 0)
        clv_count = int(totals["clv_count"] or 0)
        clv_positive = int(totals["clv_positive"] or 0)
        avg_clv = float(totals["avg_clv"]) if totals["avg_clv"] is not None else 0.0
        avg_edge = float(totals["avg_edge"]) if totals["avg_edge"] is not None else 0.0
        positive_share = (clv_positive / clv_count) if clv_count else 0.0
        avg_roi = float(roi_row["avg_roi"]) if roi_row and roi_row["avg_roi"] is not None else 0.0
        total_pages = max((total + page_size - 1) // page_size, 1)
        picks = [dict(row) for row in rows]
        return {
            "total": total,
            "avg_clv": avg_clv,
            "positive_share": positive_share,
            "avg_edge": avg_edge,
            "avg_roi": avg_roi,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "picks": picks,
        }


ledger_store = PicksLedgerStore()


__all__ = ["PicksLedgerStore", "calculate_clv", "ledger_store"]
