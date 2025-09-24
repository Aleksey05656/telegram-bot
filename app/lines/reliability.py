"""
/**
 * @file: app/lines/reliability.py
 * @description: Provider reliability tracking with exponential moving averages and persistence.
 * @dependencies: dataclasses, math, sqlite3, app.lines.providers.base, app.metrics, config
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from app.lines.providers.base import OddsSnapshot
from app.metrics import provider_fresh_share, provider_latency_ms, provider_reliability_score
from config import settings

DEFAULT_DECAY = float(getattr(settings, "RELIABILITY_DECAY", 0.9))
MAX_FRESHNESS_SEC = float(getattr(settings, "RELIABILITY_MAX_FRESHNESS_SEC", 600))
MIN_COVERAGE = float(getattr(settings, "RELIABILITY_MIN_COVERAGE", 0.6))
GLOBAL_LEAGUE = "GLOBAL"


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _from_iso(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True)
class ProviderStats:
    provider: str
    market: str
    league: str = GLOBAL_LEAGUE
    coverage: float = 0.0
    fresh_share: float = 0.0
    lag_ms: float = MAX_FRESHNESS_SEC * 1000
    stability: float = 1.0
    bias: float = 1.0
    score: float = 0.0
    sample_size: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def key(self) -> tuple[str, str, str]:
        league_key = (self.league or GLOBAL_LEAGUE).lower()
        return (self.provider.lower(), self.market.upper(), league_key)


class ProviderReliabilityStore:
    """SQLite-backed persistence for provider reliability aggregates."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.DB_PATH
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
                CREATE TABLE IF NOT EXISTS provider_stats (
                    provider TEXT NOT NULL,
                    market TEXT NOT NULL,
                    league TEXT NOT NULL,
                    coverage REAL NOT NULL,
                    fresh_share REAL NOT NULL,
                    lag_ms REAL NOT NULL,
                    stability REAL NOT NULL,
                    bias REAL NOT NULL,
                    score REAL NOT NULL,
                    sample_size INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(provider, market, league)
                )
                """
            )
            conn.commit()

    def load_all(self) -> dict[tuple[str, str, str], ProviderStats]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider, market, league, coverage, fresh_share, lag_ms,
                       stability, bias, score, sample_size, updated_at
                FROM provider_stats
                """,
            ).fetchall()
        stats: dict[tuple[str, str, str], ProviderStats] = {}
        for row in rows:
            league_raw = str(row["league"]) if row["league"] is not None else GLOBAL_LEAGUE
            league_value = (league_raw or GLOBAL_LEAGUE).upper()
            stats_obj = ProviderStats(
                provider=str(row["provider"]),
                market=str(row["market"]),
                league=league_value,
                coverage=float(row["coverage"]),
                fresh_share=float(row["fresh_share"]),
                lag_ms=float(row["lag_ms"]),
                stability=float(row["stability"]),
                bias=float(row["bias"]),
                score=float(row["score"]),
                sample_size=int(row["sample_size"]),
                updated_at=_from_iso(str(row["updated_at"])),
            )
            stats[stats_obj.key()] = stats_obj
        return stats

    def upsert_many(self, stats: Iterable[ProviderStats]) -> None:
        payload = [
            (
                item.provider,
                item.market,
                (item.league or GLOBAL_LEAGUE).upper(),
                float(item.coverage),
                float(item.fresh_share),
                float(item.lag_ms),
                float(item.stability),
                float(item.bias),
                float(item.score),
                int(item.sample_size),
                _to_iso(item.updated_at),
            )
            for item in stats
        ]
        if not payload:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO provider_stats (
                    provider, market, league, coverage, fresh_share, lag_ms,
                    stability, bias, score, sample_size, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, market, league) DO UPDATE SET
                    coverage=excluded.coverage,
                    fresh_share=excluded.fresh_share,
                    lag_ms=excluded.lag_ms,
                    stability=excluded.stability,
                    bias=excluded.bias,
                    score=excluded.score,
                    sample_size=excluded.sample_size,
                    updated_at=excluded.updated_at
                """,
                payload,
            )
            conn.commit()

    def get_stats(
        self,
        provider: str,
        market: str,
        league: str | None = None,
    ) -> ProviderStats | None:
        provider_key = provider.lower()
        market_key = market.upper()
        league_candidates = []
        if league:
            league_candidates.append(str(league).upper())
        league_candidates.append(GLOBAL_LEAGUE)
        with self._connect() as conn:
            for league_value in league_candidates:
                row = conn.execute(
                    """
                    SELECT provider, market, league, coverage, fresh_share, lag_ms,
                           stability, bias, score, sample_size, updated_at
                      FROM provider_stats
                     WHERE LOWER(provider) = ? AND market = ? AND UPPER(league) = ?
                    """,
                    (provider_key, market_key, league_value.upper()),
                ).fetchone()
                if row:
                    return ProviderStats(
                        provider=str(row["provider"]),
                        market=str(row["market"]),
                        league=str(row["league"] or GLOBAL_LEAGUE),
                        coverage=float(row["coverage"]),
                        fresh_share=float(row["fresh_share"]),
                        lag_ms=float(row["lag_ms"]),
                        stability=float(row["stability"]),
                        bias=float(row["bias"]),
                        score=float(row["score"]),
                        sample_size=int(row["sample_size"]),
                        updated_at=_from_iso(str(row["updated_at"])),
                    )
        return None


class ProviderReliabilityTracker:
    """Track reliability metrics per provider with exponential decay."""

    def __init__(
        self,
        *,
        store: ProviderReliabilityStore | None = None,
        decay: float = DEFAULT_DECAY,
        max_freshness_sec: float = MAX_FRESHNESS_SEC,
    ) -> None:
        self._store = store or ProviderReliabilityStore()
        self._decay = max(0.0, min(float(decay), 0.999))
        self._max_freshness = max(float(max_freshness_sec), 1.0)
        self._stats: dict[tuple[str, str, str], ProviderStats] = self._store.load_all()

    @property
    def decay(self) -> float:
        return self._decay

    def get(self, provider: str, market: str, league: str | None) -> ProviderStats | None:
        league_key = (league.upper() if league else GLOBAL_LEAGUE).lower()
        key = (provider.lower(), market.upper(), league_key)
        return self._stats.get(key)

    def eligible(self, provider: str, market: str, league: str | None, *, min_score: float) -> bool:
        stats = self.get(provider, market, league)
        if not stats:
            return False
        if stats.coverage < MIN_COVERAGE:
            return False
        return stats.score >= float(min_score)

    def snapshot(self) -> list[ProviderStats]:
        return list(self._stats.values())

    def observe_event(
        self,
        *,
        match_key: str,
        market: str,
        league: str | None,
        quotes: Sequence[OddsSnapshot],
        expected_providers: Iterable[str],
        reference_price: float | None,
        observed_at: datetime | None = None,
    ) -> None:
        if not expected_providers:
            return
        observed_at = observed_at or max((quote.pulled_at for quote in quotes), default=datetime.now(UTC))
        market_upper = market.upper()
        league_code = (league.upper() if league else GLOBAL_LEAGUE)
        league_key = league_code.lower()
        quotes_map = {quote.provider.lower(): quote for quote in quotes}
        median_price = self._median([quote.price_decimal for quote in quotes])
        touched: list[ProviderStats] = []
        ref_price = reference_price or median_price
        for raw_name in expected_providers:
            provider_name = raw_name.lower()
            quote = quotes_map.get(provider_name)
            stats = self._stats.get((provider_name, market_upper, league_key))
            if not stats:
                stats = ProviderStats(provider=raw_name, market=market_upper, league=league_code)
                self._stats[(provider_name, market_upper, league_key)] = stats
            stats.updated_at = observed_at
            stats.sample_size += 1
            coverage_value = 1.0 if quote else 0.0
            stats.coverage = self._ema(stats.coverage, coverage_value)
            fresh_value = 0.0
            lag_ms = stats.lag_ms
            stability_value = 0.0
            bias_value = 0.0
            if quote:
                age_sec = max((observed_at - quote.pulled_at).total_seconds(), 0.0)
                fresh_value = 1.0 if age_sec <= self._max_freshness else 0.0
                lag_ms = age_sec * 1000.0
                stability_value = self._stability_score(quote.price_decimal, median_price)
                bias_value = self._bias_score(quote.price_decimal, ref_price)
            stats.fresh_share = self._ema(stats.fresh_share, fresh_value)
            stats.lag_ms = self._ema(stats.lag_ms, lag_ms)
            stats.stability = self._ema(stats.stability, stability_value if quote else 0.0)
            stats.bias = self._ema(stats.bias, bias_value if quote else stats.bias)
            stats.score = self._compose_score(stats)
            touched.append(stats)
            league_label = stats.league if stats.league != GLOBAL_LEAGUE else GLOBAL_LEAGUE.lower()
            provider_reliability_score.labels(
                provider=stats.provider,
                market=market_upper,
                league=league_label,
            ).set(stats.score)
            provider_fresh_share.labels(
                provider=stats.provider,
                market=market_upper,
                league=league_label,
            ).set(stats.fresh_share)
            provider_latency_ms.labels(
                provider=stats.provider,
                market=market_upper,
                league=league_label,
            ).set(stats.lag_ms)
        if touched:
            self._store.upsert_many(touched)

    def _compose_score(self, stats: ProviderStats) -> float:
        lag_ratio = stats.lag_ms / (self._max_freshness * 1000.0)
        lag_score = max(0.0, 1.0 - min(lag_ratio, 1.0))
        score = (
            0.3 * stats.coverage
            + 0.25 * stats.fresh_share
            + 0.2 * stats.stability
            + 0.15 * stats.bias
            + 0.1 * lag_score
        )
        return max(0.0, min(score, 1.0))

    def _ema(self, current: float, value: float) -> float:
        if math.isnan(current):
            return value
        if self._decay <= 0.0:
            return value
        if current == 0.0 and value != 0.0 and math.isclose(self._decay, 1.0):
            return value
        return current * self._decay + value * (1.0 - self._decay)

    @staticmethod
    def _median(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        data = sorted(values)
        mid = len(data) // 2
        if len(data) % 2:
            return float(data[mid])
        return float((data[mid - 1] + data[mid]) / 2.0)

    @staticmethod
    def _stability_score(price: float, median_price: float) -> float:
        if median_price <= 0:
            return 1.0
        deviation = abs(price - median_price) / median_price
        return max(0.0, 1.0 - deviation)

    @staticmethod
    def _bias_score(price: float, reference_price: float) -> float:
        if not reference_price or reference_price <= 0:
            return 1.0
        deviation = abs(price - reference_price) / reference_price
        return max(0.0, 1.0 - deviation)


__all__ = [
    "ProviderReliabilityTracker",
    "ProviderReliabilityStore",
    "ProviderStats",
]

