"""
@file: app/value_detector.py
@description: Value betting detector comparing model probabilities with market odds.
@dependencies: dataclasses, time, app.pricing.overround, app.lines.providers.base
@created: 2025-09-24
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Iterable, Mapping

from app.lines.providers.base import OddsSnapshot
from app.metrics import (
    record_value_detector_latency,
    value_candidates_total,
    value_picks_total,
)
from app.pricing.overround import normalize_market, probabilities_to_decimal


@dataclass(slots=True)
class ModelOutcome:
    match_key: str
    market: str
    selection: str
    probability: float
    confidence: float


@dataclass(slots=True)
class ValuePick:
    match_key: str
    market: str
    selection: str
    fair_price: float
    market_price: float
    edge_pct: float
    model_probability: float
    market_probability: float
    confidence: float
    provider: str
    pulled_at: datetime
    kickoff_utc: datetime


class ValueDetector:
    def __init__(
        self,
        *,
        min_edge_pct: float,
        min_confidence: float,
        max_picks: int,
        markets: Iterable[str],
        overround_method: str = "proportional",
    ) -> None:
        self.min_edge_pct = float(min_edge_pct)
        self.min_confidence = float(min_confidence)
        self.max_picks = int(max_picks)
        self.markets = tuple(market.upper() for market in markets)
        self.overround_method = overround_method

    def detect(
        self,
        *,
        model: Iterable[ModelOutcome],
        market: Iterable[OddsSnapshot],
    ) -> list[ValuePick]:
        start = monotonic()
        picks = self._detect_impl(model=model, market=market)
        duration = monotonic() - start
        record_value_detector_latency(duration)
        value_candidates_total.inc(len(picks))
        top = picks[: self.max_picks] if self.max_picks > 0 else picks
        value_picks_total.inc(len(top))
        return top

    def _detect_impl(
        self,
        *,
        model: Iterable[ModelOutcome],
        market: Iterable[OddsSnapshot],
    ) -> list[ValuePick]:
        model_map = {
            (item.match_key, item.market.upper(), item.selection.upper()): item
            for item in model
        }
        if not model_map:
            return []
        grouped = self._group_market_quotes(market)
        candidates: list[ValuePick] = []
        for (match_key, market_name), selection_map in grouped.items():
            if self.markets and market_name.upper() not in self.markets:
                continue
            normalized = normalize_market(
                {sel: snap.price_decimal for sel, snap in selection_map.items()},
                method=self.overround_method,
            )
            for selection_key, snapshot in selection_map.items():
                model_key = (match_key, market_name.upper(), selection_key)
                model_outcome = model_map.get(model_key)
                if not model_outcome:
                    continue
                market_probability = float(normalized.get(selection_key, 0.0))
                if market_probability <= 0:
                    continue
                model_probability = float(model_outcome.probability)
                if model_probability <= 0:
                    continue
                fair_price = probabilities_to_decimal({"fair": model_probability})["fair"]
                edge_pct = (fair_price / snapshot.price_decimal - 1.0) * 100.0
                if edge_pct < self.min_edge_pct:
                    continue
                if model_outcome.confidence < self.min_confidence:
                    continue
                candidates.append(
                    ValuePick(
                        match_key=match_key,
                        market=market_name,
                        selection=selection_key,
                        fair_price=fair_price,
                        market_price=float(snapshot.price_decimal),
                        edge_pct=edge_pct,
                        model_probability=model_probability,
                        market_probability=market_probability,
                        confidence=model_outcome.confidence,
                        provider=snapshot.provider,
                        pulled_at=snapshot.pulled_at,
                        kickoff_utc=snapshot.kickoff_utc,
                    )
                )
        candidates.sort(
            key=lambda item: (item.edge_pct, item.confidence, -item.market_probability),
            reverse=True,
        )
        return candidates

    @staticmethod
    def _group_market_quotes(
        market: Iterable[OddsSnapshot],
    ) -> Mapping[tuple[str, str], dict[str, OddsSnapshot]]:
        grouped: dict[tuple[str, str], dict[str, OddsSnapshot]] = {}
        for snapshot in market:
            key = (snapshot.match_key, snapshot.market.upper())
            selection_key = snapshot.selection.upper()
            bucket = grouped.setdefault(key, {})
            existing = bucket.get(selection_key)
            if existing is None or snapshot.pulled_at > existing.pulled_at:
                bucket[selection_key] = snapshot
        return grouped


__all__ = ["ModelOutcome", "ValueDetector", "ValuePick"]
