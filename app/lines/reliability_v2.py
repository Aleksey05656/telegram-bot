"""
/**
 * @file: app/lines/reliability_v2.py
 * @description: Bayesian provider reliability tracker with exponential decay and Prometheus instrumentation.
 * @dependencies: dataclasses, sqlite3, statistics, app.lines.providers.base, app.lines.storage, app.metrics, config
 * @created: 2025-10-12
 */
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence

from app.lines.providers.base import OddsSnapshot
from app.lines.storage import LineHistoryPoint
from app.metrics import (
    provider_reliability_v2_closing,
    provider_reliability_v2_fresh,
    provider_reliability_v2_latency,
    provider_reliability_v2_score,
    provider_reliability_v2_stability,
)
from config import settings


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _from_iso(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True)
class ProviderStatsV2:
    provider: str
    league: str
    market: str
    samples: int = 0
    fresh_success: int = 0
    fresh_fail: int = 0
    latency_sum_ms: float = 0.0
    latency_sq_sum: float = 0.0
    stability_z_sum: float = 0.0
    stability_z_abs_sum: float = 0.0
    closing_within_tol: int = 0
    closing_total: int = 0
    score: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    fresh_component: float = 0.0
    latency_component: float = 0.0
    stability_component: float = 0.0
    closing_component: float = 0.0

    def key(self) -> tuple[str, str, str]:
        return (self.provider.lower(), self.league.upper(), self.market.upper())

    def apply_decay(self, decay: float) -> None:
        self.samples = int(round(self.samples * decay))
        self.fresh_success = int(round(self.fresh_success * decay))
        self.fresh_fail = int(round(self.fresh_fail * decay))
        self.latency_sum_ms *= decay
        self.latency_sq_sum *= decay
        self.stability_z_sum *= decay
        self.stability_z_abs_sum *= decay
        self.closing_within_tol = int(round(self.closing_within_tol * decay))
        self.closing_total = int(round(self.closing_total * decay))


class ProviderReliabilityStoreV2:
    """SQLite-backed persistence for Bayesian provider reliability aggregates."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.DB_PATH
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    league TEXT NOT NULL,
                    market TEXT NOT NULL,
                    samples INTEGER NOT NULL,
                    fresh_success INTEGER NOT NULL,
                    fresh_fail INTEGER NOT NULL,
                    latency_sum_ms REAL NOT NULL,
                    latency_sq_sum REAL NOT NULL,
                    stability_z_sum REAL NOT NULL,
                    stability_z_abs_sum REAL NOT NULL,
                    closing_within_tol INTEGER NOT NULL,
                    closing_total INTEGER NOT NULL,
                    score REAL NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    UNIQUE(provider, league, market)
                )
                """
            )
            conn.commit()

    def load_all(self) -> dict[tuple[str, str, str], ProviderStatsV2]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider, league, market, samples, fresh_success, fresh_fail,
                       latency_sum_ms, latency_sq_sum, stability_z_sum, stability_z_abs_sum,
                       closing_within_tol, closing_total, score, updated_at_utc
                  FROM provider_stats
                """,
            ).fetchall()
        stats: dict[tuple[str, str, str], ProviderStatsV2] = {}
        for row in rows:
            item = ProviderStatsV2(
                provider=str(row["provider"]),
                league=str(row["league"]),
                market=str(row["market"]),
                samples=int(row["samples"]),
                fresh_success=int(row["fresh_success"]),
                fresh_fail=int(row["fresh_fail"]),
                latency_sum_ms=float(row["latency_sum_ms"]),
                latency_sq_sum=float(row["latency_sq_sum"]),
                stability_z_sum=float(row["stability_z_sum"]),
                stability_z_abs_sum=float(row["stability_z_abs_sum"]),
                closing_within_tol=int(row["closing_within_tol"]),
                closing_total=int(row["closing_total"]),
                score=float(row["score"]),
                updated_at=_from_iso(str(row["updated_at_utc"])),
            )
            stats[item.key()] = item
        return stats

    def upsert_many(self, stats: Iterable[ProviderStatsV2]) -> None:
        payload = [
            (
                item.provider,
                item.league,
                item.market,
                int(item.samples),
                int(item.fresh_success),
                int(item.fresh_fail),
                float(item.latency_sum_ms),
                float(item.latency_sq_sum),
                float(item.stability_z_sum),
                float(item.stability_z_abs_sum),
                int(item.closing_within_tol),
                int(item.closing_total),
                float(item.score),
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
                    provider, league, market, samples, fresh_success, fresh_fail,
                    latency_sum_ms, latency_sq_sum, stability_z_sum, stability_z_abs_sum,
                    closing_within_tol, closing_total, score, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, league, market) DO UPDATE SET
                    samples=excluded.samples,
                    fresh_success=excluded.fresh_success,
                    fresh_fail=excluded.fresh_fail,
                    latency_sum_ms=excluded.latency_sum_ms,
                    latency_sq_sum=excluded.latency_sq_sum,
                    stability_z_sum=excluded.stability_z_sum,
                    stability_z_abs_sum=excluded.stability_z_abs_sum,
                    closing_within_tol=excluded.closing_within_tol,
                    closing_total=excluded.closing_total,
                    score=excluded.score,
                    updated_at_utc=excluded.updated_at_utc
                """,
                payload,
            )
            conn.commit()


class ProviderReliabilityV2:
    """Bayesian reliability tracker with exponential forgetting."""

    def __init__(
        self,
        *,
        store: ProviderReliabilityStoreV2 | None = None,
        decay: float | None = None,
        min_samples: int | None = None,
        scope: str | None = None,
        component_weights: Mapping[str, float] | None = None,
        prior_fresh_alpha: float | None = None,
        prior_fresh_beta: float | None = None,
        prior_latency_shape: float | None = None,
        prior_latency_scale: float | None = None,
        stability_z_tol: float | None = None,
        closing_tol_pct: float | None = None,
    ) -> None:
        self._store = store or ProviderReliabilityStoreV2()
        self._decay = max(0.0, min(float(decay or settings.RELIAB_DECAY), 0.999))
        self._min_samples = max(int(min_samples or settings.RELIAB_MIN_SAMPLES), 0)
        self._scope = (scope or settings.RELIAB_SCOPE or "league_market").lower()
        self._weights = self._parse_weights(component_weights or settings.RELIAB_COMPONENT_WEIGHTS)
        self._prior_fresh_alpha = float(prior_fresh_alpha or settings.RELIAB_PRIOR_FRESH_ALPHA)
        self._prior_fresh_beta = float(prior_fresh_beta or settings.RELIAB_PRIOR_FRESH_BETA)
        self._prior_latency_shape = float(prior_latency_shape or settings.RELIAB_PRIOR_LATENCY_SHAPE)
        self._prior_latency_scale = float(prior_latency_scale or settings.RELIAB_PRIOR_LATENCY_SCALE)
        self._stab_z_tol = max(float(stability_z_tol or settings.RELIAB_STAB_Z_TOL), 1e-6)
        self._closing_tol_pct = max(float(closing_tol_pct or settings.RELIAB_CLOSING_TOL_PCT), 0.0)
        self._fresh_window_sec = float(getattr(settings, "RELIABILITY_MAX_FRESHNESS_SEC", 600.0))
        self._stats: dict[tuple[str, str, str], ProviderStatsV2] = self._store.load_all()
        self._closing_seen: set[str] = set()

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
        providers = list(expected_providers)
        if not providers:
            return
        observed_at = observed_at or datetime.now(UTC)
        league_norm = league.upper() if league else "GLOBAL"
        market_norm = market.upper()
        quotes_map = {quote.provider.lower(): quote for quote in quotes}
        implied = [1.0 / quote.price_decimal for quote in quotes if quote.price_decimal > 0]
        mean_prob = fmean(implied) if implied else 0.0
        std_prob = pstdev(implied) if len(implied) >= 2 else 0.0
        touched: list[ProviderStatsV2] = []
        for raw_name in providers:
            provider_name = str(raw_name)
            stats = self._get_or_create(provider_name, league_norm, market_norm)
            stats.apply_decay(self._decay)
            stats.samples += 1
            quote = quotes_map.get(provider_name.lower())
            if quote is None:
                stats.fresh_fail += 1
            else:
                latency_sec = max((observed_at - quote.pulled_at).total_seconds(), 0.0)
                latency_ms = latency_sec * 1000.0
                is_fresh = latency_sec <= self._fresh_window_sec
                if is_fresh:
                    stats.fresh_success += 1
                else:
                    stats.fresh_fail += 1
                stats.latency_sum_ms += latency_ms
                stats.latency_sq_sum += latency_ms * latency_ms
                if std_prob > 0:
                    price_prob = 1.0 / quote.price_decimal if quote.price_decimal > 0 else mean_prob
                    z_value = (price_prob - mean_prob) / std_prob
                else:
                    z_value = 0.0
                stats.stability_z_sum += z_value
                stats.stability_z_abs_sum += abs(z_value)
            stats.updated_at = observed_at
            self._update_components(stats)
            touched.append(stats)
        if touched:
            self._store.upsert_many(touched)

    def observe_closing(
        self,
        *,
        match_key: str,
        market: str,
        league: str | None,
        selection: str,
        closing_price: float | None,
        closing_pulled_at: datetime | None,
        history: Sequence[LineHistoryPoint] | None,
    ) -> None:
        if not closing_price or closing_price <= 0:
            return
        if closing_pulled_at is None:
            return
        if not history:
            return
        event_key = "|".join(
            [
                match_key,
                market.upper(),
                selection.upper(),
                closing_pulled_at.astimezone(UTC).isoformat(),
            ]
        )
        if event_key in self._closing_seen:
            return
        self._closing_seen.add(event_key)
        tolerance = self._closing_tol_pct / 100.0
        cutoff = closing_pulled_at.astimezone(UTC)
        latest_per_provider: dict[str, LineHistoryPoint] = {}
        for point in history:
            pulled = point.pulled_at.astimezone(UTC)
            if pulled > cutoff:
                continue
            key = point.provider.lower()
            current = latest_per_provider.get(key)
            if current is None or pulled > current.pulled_at.astimezone(UTC):
                latest_per_provider[key] = point
        if not latest_per_provider:
            return
        league_norm = league.upper() if league else "GLOBAL"
        market_norm = market.upper()
        touched: list[ProviderStatsV2] = []
        for key, point in latest_per_provider.items():
            stats = self._get_or_create(point.provider, league_norm, market_norm)
            stats.closing_total += 1
            diff_pct = abs(point.price_decimal - closing_price) / closing_price
            if diff_pct <= tolerance:
                stats.closing_within_tol += 1
            stats.updated_at = closing_pulled_at
            self._update_components(stats)
            touched.append(stats)
        if touched:
            self._store.upsert_many(touched)

    def eligible(self, provider: str, market: str, league: str | None, *, min_score: float) -> bool:
        stats = self.get(provider, market, league)
        if not stats:
            return False
        if stats.samples < self._min_samples:
            return False
        return stats.score >= float(min_score)

    def get(self, provider: str, market: str, league: str | None) -> ProviderStatsV2 | None:
        league_norm = league.upper() if league else "GLOBAL"
        market_norm = market.upper()
        for key in self._key_variants(provider, league_norm, market_norm):
            stats = self._stats.get(key)
            if stats:
                return stats
        return None

    def snapshot(self) -> list[ProviderStatsV2]:
        return list(self._stats.values())

    def get_provider_scores(self, league: str, market: str) -> dict[str, float]:
        league_norm = league.upper() if league else "GLOBAL"
        market_norm = market.upper()
        scores: dict[str, float] = {}
        for stats in self._stats.values():
            if self._matches_scope(stats.league, stats.market, league_norm, market_norm):
                scores[stats.provider] = float(stats.score)
        return scores

    def explain_components(self, provider: str, league: str, market: str) -> dict[str, float]:
        stats = self.get(provider, market, league)
        if not stats:
            return {}
        return {
            "fresh": float(stats.fresh_component),
            "latency": float(stats.latency_component),
            "stability": float(stats.stability_component),
            "closing": float(stats.closing_component),
            "score": float(stats.score),
        }

    def _get_or_create(self, provider: str, league: str, market: str) -> ProviderStatsV2:
        key = self._scope_key(provider, league, market)
        stats = self._stats.get(key)
        if stats:
            return stats
        stats = ProviderStatsV2(provider=provider, league=key[1], market=key[2])
        self._stats[key] = stats
        return stats

    def _scope_key(self, provider: str, league: str, market: str) -> tuple[str, str, str]:
        provider_key = provider.lower()
        league_norm = league.upper()
        market_norm = market.upper()
        if self._scope == "global":
            return (provider_key, "GLOBAL", "GLOBAL")
        if self._scope == "league":
            return (provider_key, league_norm, "GLOBAL")
        return (provider_key, league_norm, market_norm)

    def _matches_scope(self, stats_league: str, stats_market: str, league: str, market: str) -> bool:
        if self._scope == "global":
            return stats_league == "GLOBAL" and stats_market == "GLOBAL"
        if self._scope == "league":
            return stats_league == league and stats_market == "GLOBAL"
        return stats_league == league and stats_market == market

    def _key_variants(self, provider: str, league: str, market: str) -> list[tuple[str, str, str]]:
        provider_key = provider.lower()
        league_norm = league.upper()
        market_norm = market.upper()
        variants = [(provider_key, league_norm, market_norm)]
        if self._scope == "league_market":
            variants.append((provider_key, league_norm, "GLOBAL"))
        variants.append((provider_key, "GLOBAL", "GLOBAL"))
        return variants

    def _update_components(self, stats: ProviderStatsV2) -> None:
        total_weight = sum(self._weights.values()) or 1.0
        fresh_total = max(stats.fresh_success + stats.fresh_fail, 0)
        fresh_component = (
            (self._prior_fresh_alpha + stats.fresh_success)
            / (self._prior_fresh_alpha + self._prior_fresh_beta + fresh_total)
            if (self._prior_fresh_alpha + self._prior_fresh_beta + fresh_total) > 0
            else 0.0
        )
        provided = max(stats.fresh_success + stats.fresh_fail, 0)
        posterior_shape = self._prior_latency_shape + provided
        if posterior_shape <= 0:
            latency_expectation = 0.0
        else:
            posterior_scale = (
                self._prior_latency_shape * self._prior_latency_scale + stats.latency_sum_ms
            ) / max(posterior_shape, 1.0)
            latency_expectation = posterior_shape * max(posterior_scale, 0.0)
        baseline_latency = max(self._prior_latency_shape * self._prior_latency_scale, 1.0)
        latency_component = 1.0 / (1.0 + latency_expectation / baseline_latency)
        avg_abs_z = (
            stats.stability_z_abs_sum / provided if provided > 0 else 0.0
        )
        stability_component = max(0.0, 1.0 - avg_abs_z / self._stab_z_tol)
        closing_component = (
            (stats.closing_within_tol + 1) / (stats.closing_total + 2)
            if stats.closing_total > 0
            else 0.5
        )
        weighted_sum = (
            self._weights["fresh"] * fresh_component
            + self._weights["latency"] * latency_component
            + self._weights["stability"] * stability_component
            + self._weights["closing_bias"] * closing_component
        )
        stats.fresh_component = fresh_component
        stats.latency_component = latency_component
        stats.stability_component = stability_component
        stats.closing_component = closing_component
        stats.score = max(0.0, min(weighted_sum / total_weight, 1.0))
        self._publish_metrics(stats)

    def _publish_metrics(self, stats: ProviderStatsV2) -> None:
        provider_reliability_v2_score.labels(
            provider=stats.provider,
            league=stats.league,
            market=stats.market,
        ).set(stats.score)
        provider_reliability_v2_fresh.labels(
            provider=stats.provider,
            league=stats.league,
            market=stats.market,
        ).set(stats.fresh_component)
        provider_reliability_v2_latency.labels(
            provider=stats.provider,
            league=stats.league,
            market=stats.market,
        ).set(stats.latency_component)
        provider_reliability_v2_stability.labels(
            provider=stats.provider,
            league=stats.league,
            market=stats.market,
        ).set(stats.stability_component)
        provider_reliability_v2_closing.labels(
            provider=stats.provider,
            league=stats.league,
            market=stats.market,
        ).set(stats.closing_component)

    @staticmethod
    def _parse_weights(raw: Mapping[str, float] | str) -> dict[str, float]:
        if isinstance(raw, Mapping):
            weights = {str(k).strip().lower(): float(v) for k, v in raw.items()}
        else:
            weights = {}
            for chunk in str(raw).split(","):
                if not chunk.strip() or ":" not in chunk:
                    continue
                name, value = chunk.split(":", 1)
                try:
                    weights[name.strip().lower()] = float(value)
                except ValueError:
                    continue
        defaults = {
            "fresh": 0.35,
            "latency": 0.15,
            "stability": 0.30,
            "closing_bias": 0.20,
        }
        defaults.update({key: value for key, value in weights.items() if value >= 0})
        return defaults


_GLOBAL_TRACKER: ProviderReliabilityV2 | None = None


def get_tracker() -> ProviderReliabilityV2:
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        _GLOBAL_TRACKER = ProviderReliabilityV2()
    return _GLOBAL_TRACKER


def get_provider_scores(league: str, market: str) -> dict[str, float]:
    return get_tracker().get_provider_scores(league, market)


def explain_components(provider: str, league: str, market: str) -> dict[str, float]:
    return get_tracker().explain_components(provider, league, market)


__all__ = [
    "ProviderReliabilityStoreV2",
    "ProviderReliabilityV2",
    "ProviderStatsV2",
    "explain_components",
    "get_provider_scores",
    "get_tracker",
]

