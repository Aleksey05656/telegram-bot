"""
/**
 * @file: app/lines/aggregator.py
 * @description: Multi-provider odds aggregation with consensus strategies and movement analysis.
 * @dependencies: dataclasses, statistics, app.lines.providers.base, app.lines.storage, app.lines.movement
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from statistics import median

from app.lines.anomaly import OddsAnomalyDetector
from app.lines.movement import MovementResult, analyze_movement
from app.lines.providers.base import LinesProvider, OddsSnapshot
from app.lines.reliability import ProviderReliabilityTracker
from app.lines.reliability_v2 import ProviderReliabilityV2
from app.lines.storage import LineHistoryPoint, OddsSQLiteStore
from config import settings


@dataclass(slots=True, frozen=True)
class ProviderQuote:
    provider: str
    price_decimal: float
    pulled_at: datetime


@dataclass(slots=True, frozen=True)
class ConsensusMeta:
    match_key: str
    market: str
    selection: str
    price_decimal: float
    probability: float
    method: str
    provider_count: int
    providers: tuple[ProviderQuote, ...]
    trend: str
    pulled_at: datetime
    league: str | None
    kickoff_utc: datetime
    closing_price: float | None = None
    closing_pulled_at: datetime | None = None


class LinesAggregator:
    """Calculate consensus odds from multiple providers."""

    def __init__(
        self,
        *,
        method: str = "median",
        provider_weights: Mapping[str, float] | None = None,
        store: OddsSQLiteStore | None = None,
        retention_days: int = 7,
        movement_window_minutes: int = 60,
        movement_tolerance_pct: float = 0.5,
        reliability: ProviderReliabilityTracker | ProviderReliabilityV2 | None = None,
        anomaly_detector: OddsAnomalyDetector | None = None,
        known_providers: Iterable[str] | None = None,
        best_price_lookback_min: int | None = None,
        best_price_min_score: float | None = None,
    ) -> None:
        self.method = method.lower().strip() or "median"
        self._weights = {
            key.strip().lower(): float(value)
            for key, value in (provider_weights or {}).items()
            if float(value) > 0
        }
        self._store = store
        self._retention_days = max(int(retention_days), 0)
        self._movement_window = max(int(movement_window_minutes), 0)
        self._movement_tolerance = float(movement_tolerance_pct)
        self._last_meta: MutableMapping[tuple[str, str, str], ConsensusMeta] = {}
        self._reliability = reliability
        self._anomaly_detector = anomaly_detector
        self._known_providers: tuple[str, ...] | None = self._normalize_providers(known_providers)
        if not self._known_providers and provider_weights:
            self._known_providers = self._normalize_providers(provider_weights.keys())
        default_lookback = getattr(settings, "BEST_PRICE_LOOKBACK_MIN", 15)
        default_score = getattr(settings, "BEST_PRICE_MIN_SCORE", 0.6)
        self._best_price_lookback_min = int(best_price_lookback_min or default_lookback)
        self._best_price_min_score = float(best_price_min_score or default_score)

    @property
    def last_metadata(self) -> dict[tuple[str, str, str], ConsensusMeta]:
        return dict(self._last_meta)

    def aggregate(self, snapshots: Iterable[OddsSnapshot]) -> list[OddsSnapshot]:
        rows = list(snapshots)
        if not rows:
            self._last_meta.clear()
            return []
        if self._store:
            self._store.upsert_many(rows)
            if self._retention_days:
                self._store.purge_older_than(self._retention_days)
        grouped: dict[tuple[str, str, str], list[OddsSnapshot]] = defaultdict(list)
        for item in rows:
            key = (item.match_key, item.market.upper(), item.selection.upper())
            grouped[key].append(item)
        consensus_rows: list[OddsSnapshot] = []
        self._last_meta.clear()
        for key, items in grouped.items():
            quotes = self._latest_per_provider(items)
            if not quotes:
                continue
            league = next((quote.league for quote in quotes if quote.league), None)
            probability = self._consensus_probability(quotes, league)
            if probability is None or probability <= 0:
                continue
            price = 1.0 / probability
            latest = max(quotes, key=lambda q: q.pulled_at)
            kickoff = quotes[0].kickoff_utc
            movement = self._movement(
                quotes,
                kickoff,
                match_key=latest.match_key,
                market=latest.market,
                selection=latest.selection,
                league=league,
            )
            consensus = OddsSnapshot(
                provider="consensus",
                pulled_at=latest.pulled_at,
                match_key=latest.match_key,
                league=league,
                kickoff_utc=kickoff,
                market=latest.market,
                selection=latest.selection,
                price_decimal=price,
                extra={
                    "consensus": {
                        "method": self.method,
                        "probability": probability,
                        "provider_count": len(quotes),
                        "trend": movement.trend,
                        "closing_price": movement.closing_price,
                        "closing_pulled_at": movement.closing_pulled_at.isoformat().replace(
                            "+00:00", "Z"
                        )
                        if movement.closing_pulled_at
                        else None,
                        "match_key": latest.match_key,
                        "market": latest.market,
                        "selection": latest.selection,
                        "league": league,
                        "kickoff_utc": kickoff.astimezone(UTC)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "providers": [
                            {
                                "name": quote.provider,
                                "price_decimal": quote.price_decimal,
                                "pulled_at": quote.pulled_at.astimezone(UTC)
                                .isoformat()
                                .replace("+00:00", "Z"),
                            }
                            for quote in quotes
                        ],
                        "pulled_at": latest.pulled_at.astimezone(UTC)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "price_decimal": price,
                    }
                },
            )
            self._last_meta[key] = ConsensusMeta(
                match_key=latest.match_key,
                market=latest.market,
                selection=latest.selection,
                price_decimal=price,
                probability=probability,
                method=self.method,
                provider_count=len(quotes),
                providers=tuple(quotes),
                trend=movement.trend,
                pulled_at=latest.pulled_at,
                league=league,
                kickoff_utc=kickoff,
                closing_price=movement.closing_price,
                closing_pulled_at=movement.closing_pulled_at,
            )
            if self._reliability:
                expected = self._known_providers or self._normalize_providers(
                    quote.provider for quote in items
                )
                self._reliability.observe_event(
                    match_key=latest.match_key,
                    market=latest.market.upper(),
                    league=league,
                    quotes=quotes,
                    expected_providers=expected,
                    reference_price=movement.closing_price or price,
                    observed_at=latest.pulled_at,
                )
            consensus_rows.append(consensus)
        return consensus_rows

    def pick_best_route(
        self,
        *,
        match_key: str,
        market: str,
        selection: str,
        league: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, object] | None:
        if not self._store:
            return None
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(minutes=max(self._best_price_lookback_min, 1))
        market_upper = market.upper()
        latest = self._store.latest_quotes(
            match_key=match_key,
            market=market_upper,
            selection=selection.upper(),
        )
        candidates = [quote for quote in latest if quote.pulled_at >= cutoff]
        if not candidates:
            return None
        flagged: set[str] = set()
        if self._anomaly_detector:
            flagged = self._anomaly_detector.filter_anomalies(candidates)
        league_name = league or next((item.league for item in candidates if item.league), None)
        best_quote: OddsSnapshot | None = None
        best_score = 0.0
        for snapshot in candidates:
            provider_id = snapshot.provider
            if snapshot.provider.lower() in flagged:
                continue
            score = 1.0
            if self._reliability:
                if not self._reliability.eligible(
                    provider_id,
                    market_upper,
                    league_name,
                    min_score=self._best_price_min_score,
                ):
                    continue
                stats = self._reliability.get(provider_id, market_upper, league_name)
                if not stats:
                    continue
                score = float(stats.score)
            if best_quote is None or snapshot.price_decimal > best_quote.price_decimal:
                best_quote = snapshot
                best_score = score
        if not best_quote:
            return None
        return {
            "provider": best_quote.provider,
            "price_decimal": float(best_quote.price_decimal),
            "pulled_at_utc": best_quote.pulled_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "score": float(best_score),
        }

    @property
    def reliability_tracker(self) -> ProviderReliabilityTracker | ProviderReliabilityV2 | None:
        return self._reliability

    @property
    def anomaly_detector(self) -> OddsAnomalyDetector | None:
        return self._anomaly_detector

    @property
    def store(self) -> OddsSQLiteStore | None:
        return self._store

    def register_providers(self, providers: Iterable[str]) -> None:
        names = self._normalize_providers(providers)
        if names:
            self._known_providers = names

    @staticmethod
    def _normalize_providers(providers: Iterable[str] | None) -> tuple[str, ...] | None:
        if not providers:
            return None
        seen: dict[str, None] = {}
        for name in providers:
            if not name:
                continue
            seen[str(name)] = None
        return tuple(seen.keys()) if seen else None

    def _latest_per_provider(self, items: Sequence[OddsSnapshot]) -> list[OddsSnapshot]:
        by_provider: dict[str, OddsSnapshot] = {}
        for snapshot in sorted(items, key=lambda row: row.pulled_at):
            by_provider[snapshot.provider.lower()] = snapshot
        ordered = list(by_provider.values())
        ordered.sort(key=lambda row: row.price_decimal, reverse=True)
        return ordered

    def _consensus_probability(
        self,
        quotes: Sequence[OddsSnapshot],
        league: str | None,
    ) -> float | None:
        implied = [1.0 / quote.price_decimal for quote in quotes if quote.price_decimal > 0]
        if not implied:
            return None
        if self.method == "best":
            return min(implied)
        if self.method == "median":
            return float(median(implied))
        if self.method == "weighted":
            weighted_sum = 0.0
            total_weight = 0.0
            for quote in quotes:
                weight = self._weights.get(quote.provider.lower(), 1.0)
                if (
                    getattr(settings, "RELIAB_V2_ENABLE", False)
                    and isinstance(self._reliability, ProviderReliabilityV2)
                ):
                    stats = self._reliability.get(quote.provider, quote.market.upper(), league)
                    if stats and stats.score > 0:
                        weight = float(stats.score)
                weighted_sum += (1.0 / quote.price_decimal) * weight
                total_weight += weight
            if total_weight <= 0:
                return float(median(implied))
            return weighted_sum / total_weight
        return float(median(implied))

    def _movement(
        self,
        quotes: Sequence[OddsSnapshot],
        kickoff: datetime,
        *,
        match_key: str,
        market: str,
        selection: str,
        league: str | None,
    ) -> MovementResult:
        if not self._store:
            return MovementResult(trend="→")
        key = (quotes[0].match_key, quotes[0].market.upper(), quotes[0].selection.upper())
        history = self._store.history(
            match_key=key[0],
            market=key[1],
            selection=key[2],
        )
        if not history:
            history = [
                LineHistoryPoint(
                    provider=quote.provider,
                    pulled_at=quote.pulled_at,
                    price_decimal=quote.price_decimal,
                )
                for quote in quotes
            ]
        reliability = None
        if getattr(settings, "RELIAB_V2_ENABLE", False) and isinstance(
            self._reliability, ProviderReliabilityV2
        ):
            reliability = self._reliability
        return analyze_movement(
            history,
            kickoff=kickoff,
            window_minutes=self._movement_window,
            tolerance_pct=self._movement_tolerance,
            reliability=reliability,
            match_key=match_key,
            market=market,
            league=league,
            selection=selection,
        )


class AggregatingLinesProvider:
    """Compose multiple providers into a consensus feed."""

    def __init__(
        self,
        providers: Mapping[str, LinesProvider],
        *,
        aggregator: LinesAggregator,
    ) -> None:
        self._providers = dict(providers)
        self._aggregator = aggregator
        self._aggregator.register_providers(self._providers.keys())

    async def fetch_odds(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        leagues: Sequence[str] | None = None,
    ) -> list[OddsSnapshot]:
        rows: list[OddsSnapshot] = []
        for name, provider in self._providers.items():
            snapshots = await provider.fetch_odds(date_from=date_from, date_to=date_to, leagues=leagues)
            normalized = [
                replace(snapshot, provider=name)
                if snapshot.provider.lower() != name.lower()
                else snapshot
                for snapshot in snapshots
            ]
            rows.extend(normalized)
        return self._aggregator.aggregate(rows)

    async def close(self) -> None:
        for provider in self._providers.values():
            close_fn = getattr(provider, "close", None)
            if not close_fn:
                continue
            result = close_fn()
            if hasattr(result, "__await__"):
                await result

    @property
    def aggregator(self) -> LinesAggregator:
        return self._aggregator


def parse_provider_weights(raw: str | Mapping[str, float] | None) -> dict[str, float]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return {str(key).strip().lower(): float(value) for key, value in raw.items() if float(value) > 0}
    result: dict[str, float] = {}
    for chunk in str(raw).split(","):
        if not chunk.strip():
            continue
        if ":" not in chunk:
            result[chunk.strip().lower()] = 1.0
            continue
        name, value = chunk.split(":", 1)
        try:
            weight = float(value)
        except ValueError:
            continue
        if weight > 0:
            result[name.strip().lower()] = weight
    return result


__all__ = [
    "AggregatingLinesProvider",
    "ConsensusMeta",
    "LinesAggregator",
    "ProviderQuote",
    "parse_provider_weights",
]
