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
from datetime import UTC, datetime
from statistics import median

from app.lines.movement import MovementResult, analyze_movement
from app.lines.providers.base import LinesProvider, OddsSnapshot
from app.lines.storage import LineHistoryPoint, OddsSQLiteStore


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
            probability = self._consensus_probability(quotes)
            if probability is None or probability <= 0:
                continue
            price = 1.0 / probability
            latest = max(quotes, key=lambda q: q.pulled_at)
            kickoff = quotes[0].kickoff_utc
            league = next((quote.league for quote in quotes if quote.league), None)
            movement = self._movement(quotes, kickoff)
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
            consensus_rows.append(consensus)
        return consensus_rows

    def _latest_per_provider(self, items: Sequence[OddsSnapshot]) -> list[OddsSnapshot]:
        by_provider: dict[str, OddsSnapshot] = {}
        for snapshot in sorted(items, key=lambda row: row.pulled_at):
            by_provider[snapshot.provider.lower()] = snapshot
        ordered = list(by_provider.values())
        ordered.sort(key=lambda row: row.price_decimal, reverse=True)
        return ordered

    def _consensus_probability(self, quotes: Sequence[OddsSnapshot]) -> float | None:
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
                weighted_sum += (1.0 / quote.price_decimal) * weight
                total_weight += weight
            if total_weight <= 0:
                return float(median(implied))
            return weighted_sum / total_weight
        return float(median(implied))

    def _movement(self, quotes: Sequence[OddsSnapshot], kickoff: datetime) -> MovementResult:
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
        return analyze_movement(
            history,
            kickoff=kickoff,
            window_minutes=self._movement_window,
            tolerance_pct=self._movement_tolerance,
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
