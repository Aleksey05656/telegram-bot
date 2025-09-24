"""
@file: app/value_detector.py
@description: Value betting detector comparing model probabilities with market odds.
@dependencies: dataclasses, time, app.pricing.overround, app.lines.providers.base
@created: 2025-09-24
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Iterable, Mapping

from app.lines.providers.base import OddsSnapshot
from app.metrics import (
    record_value_detector_latency,
    value_candidates_total,
    value_confidence_avg,
    value_edge_weighted_avg,
    value_picks_total,
)
from app.pricing.overround import normalize_market, probabilities_to_decimal
from app.value_calibration import CalibrationRecord, CalibrationService


@dataclass(slots=True)
class ModelOutcome:
    match_key: str
    market: str
    selection: str
    probability: float
    confidence: float
    probability_variance: float | None = None


@dataclass(slots=True)
class ValuePick:
    match_key: str
    market: str
    selection: str
    league: str | None
    fair_price: float
    market_price: float
    edge_pct: float
    model_probability: float
    market_probability: float
    confidence: float
    edge_weighted_pct: float
    edge_threshold_pct: float
    confidence_threshold: float
    calibrated: bool
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
        confidence_method: str = "none",
        calibration: CalibrationService | None = None,
    ) -> None:
        self.min_edge_pct = float(min_edge_pct)
        self.min_confidence = float(min_confidence)
        self.max_picks = int(max_picks)
        self.markets = tuple(market.upper() for market in markets)
        self.overround_method = overround_method
        self._confidence_method = confidence_method.lower().strip() or "none"
        self._calibration = calibration

    def detect(
        self,
        *,
        model: Iterable[ModelOutcome],
        market: Iterable[OddsSnapshot],
    ) -> list[ValuePick]:
        start = monotonic()
        candidates = self._detect_impl(model=model, market=market)
        duration = monotonic() - start
        record_value_detector_latency(duration)
        value_candidates_total.inc(len(candidates))
        top = candidates[: self.max_picks] if self.max_picks > 0 else candidates
        value_picks_total.inc(len(top))
        if top:
            avg_conf = sum(item.confidence for item in top) / len(top)
            avg_edge_w = sum(item.edge_weighted_pct for item in top) / len(top)
            value_confidence_avg.set(avg_conf)
            value_edge_weighted_avg.set(avg_edge_w)
        else:
            value_confidence_avg.set(0.0)
            value_edge_weighted_avg.set(0.0)
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
        for (match_key, market_name), payload in grouped.items():
            league_name, selection_map = payload
            if self.markets and market_name.upper() not in self.markets:
                continue
            calibration = self._resolve_thresholds(league_name, market_name)
            edge_threshold = max(self.min_edge_pct, calibration.tau_edge)
            confidence_threshold = max(self.min_confidence, calibration.gamma_conf)
            calibrated_flag = bool(self._calibration and calibration.samples > 0)
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
                confidence = self._compute_confidence(model_outcome)
                edge_weighted = edge_pct * confidence
                if edge_pct < edge_threshold:
                    continue
                if confidence < confidence_threshold:
                    continue
                candidates.append(
                    ValuePick(
                        match_key=match_key,
                        market=market_name,
                        selection=selection_key,
                        league=league_name,
                        fair_price=fair_price,
                        market_price=float(snapshot.price_decimal),
                        edge_pct=edge_pct,
                        model_probability=model_probability,
                        market_probability=market_probability,
                        confidence=confidence,
                        edge_weighted_pct=edge_weighted,
                        edge_threshold_pct=edge_threshold,
                        confidence_threshold=confidence_threshold,
                        calibrated=calibrated_flag,
                        provider=snapshot.provider,
                        pulled_at=snapshot.pulled_at,
                        kickoff_utc=snapshot.kickoff_utc,
                    )
                )
        candidates.sort(
            key=lambda item: (
                item.edge_weighted_pct,
                item.confidence,
                item.edge_pct,
                -item.market_probability,
            ),
            reverse=True,
        )
        return candidates

    @staticmethod
    def _group_market_quotes(
        market: Iterable[OddsSnapshot],
    ) -> Mapping[tuple[str, str], tuple[str | None, dict[str, OddsSnapshot]]]:
        grouped: dict[tuple[str, str], dict[str, OddsSnapshot]] = {}
        leagues: dict[tuple[str, str], str | None] = {}
        for snapshot in market:
            key = (snapshot.match_key, snapshot.market.upper())
            selection_key = snapshot.selection.upper()
            bucket = grouped.setdefault(key, {})
            existing = bucket.get(selection_key)
            if existing is None or snapshot.pulled_at > existing.pulled_at:
                bucket[selection_key] = snapshot
                leagues[key] = snapshot.league
        return {key: (leagues.get(key), value) for key, value in grouped.items()}

    def _resolve_thresholds(self, league: str | None, market: str) -> CalibrationRecord:
        if not self._calibration:
            return CalibrationRecord(
                league=league or "",
                market=market,
                tau_edge=self.min_edge_pct,
                gamma_conf=self.min_confidence,
                samples=0,
                metric=0.0,
                updated_at=datetime.now(UTC),
            )
        return self._calibration.thresholds_for(league, market)

    def _compute_confidence(self, outcome: ModelOutcome) -> float:
        base = max(0.0, min(1.0, float(outcome.confidence)))
        if self._confidence_method != "mc_var":
            return base
        variance = max(float(outcome.probability_variance or 0.0), 0.0)
        mc_conf = 1.0 / (1.0 + variance)
        return max(0.0, min(1.0, mc_conf))


__all__ = ["ModelOutcome", "ValueDetector", "ValuePick"]
