"""
@file: app/value_service.py
@description: Orchestrates fetching predictions and odds to surface value picks and comparisons.
@dependencies: datetime, app.bot.services, app.lines, app.value_detector
@created: 2025-09-24
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable, Sequence

from app.bot.services import Prediction, PredictionFacade
from app.lines.mapper import LinesMapper
from app.lines.providers.base import LinesProvider, OddsSnapshot
from app.pricing.overround import normalize_market
from app.value_detector import ModelOutcome, ValueDetector, ValuePick


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


@dataclass(slots=True)
class ValueService:
    facade: PredictionFacade
    provider: LinesProvider
    detector: ValueDetector
    mapper: LinesMapper = field(default_factory=LinesMapper)

    async def value_picks(
        self,
        *,
        target_date: date,
        league: str | None,
    ) -> list[dict[str, object]]:
        predictions = await self.facade.today(target_date, league=league)
        meta: dict[str, dict[str, object]] = {}
        model = list(self._build_model_outcomes(predictions, meta))
        if not model:
            return []
        odds = await self.provider.fetch_odds(
            date_from=_start_of_day(target_date),
            date_to=_end_of_day(target_date),
            leagues=[league] if league else None,
        )
        picks = self.detector.detect(model=model, market=odds)
        cards: list[dict[str, object]] = []
        for pick in picks:
            info = meta.get(pick.match_key, {})
            cards.append(
                {
                    "match": info,
                    "pick": pick,
                    "overround_method": self.detector.overround_method,
                }
            )
        return cards

    async def compare(
        self,
        *,
        query: str,
        target_date: date,
    ) -> dict[str, object] | None:
        predictions = await self.facade.today(target_date)
        prediction = self._find_prediction(predictions, query)
        if prediction is None:
            return None
        normalized = self.mapper.normalize_row(
            {
                "home": prediction.home,
                "away": prediction.away,
                "league": prediction.league,
                "kickoff_utc": prediction.kickoff,
            }
        )
        match_key = normalized["match_key"]
        odds = await self.provider.fetch_odds(
            date_from=prediction.kickoff - timedelta(days=1),
            date_to=prediction.kickoff + timedelta(days=1),
        )
        odds_for_match = [item for item in odds if item.match_key == match_key]
        model_outcomes = list(self._build_model_outcomes([prediction]))
        detector_results = self.detector.detect(model=model_outcomes, market=odds_for_match)
        markets_summary = self._build_comparison(model_outcomes, odds_for_match)
        return {
            "match": {
                "home": prediction.home,
                "away": prediction.away,
                "league": prediction.league,
                "kickoff": prediction.kickoff,
                "match_key": match_key,
            },
            "picks": detector_results,
            "markets": markets_summary,
            "overround_method": self.detector.overround_method,
        }

    def _build_model_outcomes(
        self,
        predictions: Sequence[Prediction],
        meta: dict[str, dict[str, object]] | None = None,
    ) -> Iterable[ModelOutcome]:
        for prediction in predictions:
            normalized = self.mapper.normalize_row(
                {
                    "home": prediction.home,
                    "away": prediction.away,
                    "league": prediction.league,
                    "kickoff_utc": prediction.kickoff,
                }
            )
            match_key = normalized["match_key"]
            confidence = float(prediction.confidence)
            if meta is not None and match_key not in meta:
                meta[match_key] = {
                    "home": prediction.home,
                    "away": prediction.away,
                    "league": prediction.league,
                    "kickoff": prediction.kickoff,
                    "match_key": match_key,
                }
            markets = prediction.markets or {}
            one_x_two = markets.get("1x2") or {}
            mapping = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}
            for key, alias in mapping.items():
                prob = one_x_two.get(key)
                if prob is None:
                    continue
                yield ModelOutcome(
                    match_key=match_key,
                    market="1X2",
                    selection=alias,
                    probability=float(prob),
                    confidence=confidence,
                )
            totals = prediction.totals or {}
            totals_2_5 = totals.get("2.5") or {}
            if totals_2_5:
                yield ModelOutcome(
                    match_key=match_key,
                    market="OU_2_5",
                    selection="OVER",
                    probability=float(totals_2_5.get("over", 0.0)),
                    confidence=confidence,
                )
                yield ModelOutcome(
                    match_key=match_key,
                    market="OU_2_5",
                    selection="UNDER",
                    probability=float(totals_2_5.get("under", 0.0)),
                    confidence=confidence,
                )
            btts = prediction.btts or {}
            if btts:
                yield ModelOutcome(
                    match_key=match_key,
                    market="BTTS",
                    selection="YES",
                    probability=float(btts.get("yes", 0.0)),
                    confidence=confidence,
                )
                yield ModelOutcome(
                    match_key=match_key,
                    market="BTTS",
                    selection="NO",
                    probability=float(btts.get("no", 0.0)),
                    confidence=confidence,
                )

    def _find_prediction(
        self,
        predictions: Sequence[Prediction],
        query: str,
    ) -> Prediction | None:
        query_normalized = query.strip().lower()
        if not query_normalized:
            return None
        if query_normalized.isdigit():
            match_id = int(query_normalized)
            for prediction in predictions:
                if prediction.match_id == match_id:
                    return prediction
        for prediction in predictions:
            composite = f"{prediction.home} {prediction.away}".lower()
            if query_normalized in composite:
                return prediction
        return predictions[0] if predictions else None

    def _build_comparison(
        self,
        model_outcomes: Sequence[ModelOutcome],
        odds: Sequence[OddsSnapshot],
    ) -> dict[str, dict[str, dict[str, float]]]:
        grouped: dict[str, dict[str, dict[str, float]]] = {}
        outcomes_by_market: dict[str, dict[str, ModelOutcome]] = {}
        for outcome in model_outcomes:
            market_bucket = outcomes_by_market.setdefault(outcome.market, {})
            market_bucket[outcome.selection] = outcome
        grouped_odds: dict[str, dict[str, OddsSnapshot]] = {}
        for snapshot in odds:
            market_bucket = grouped_odds.setdefault(snapshot.market.upper(), {})
            selection_key = snapshot.selection.upper()
            current = market_bucket.get(selection_key)
            if current is None or snapshot.pulled_at > current.pulled_at:
                market_bucket[selection_key] = snapshot
        for market_name, selections in grouped_odds.items():
            norm = normalize_market(
                {sel: snap.price_decimal for sel, snap in selections.items()}
            )
            market_summary: dict[str, dict[str, float]] = {}
            for selection_key, snapshot in selections.items():
                model_outcome = outcomes_by_market.get(market_name, {}).get(selection_key)
                if not model_outcome:
                    continue
                market_summary[selection_key] = {
                    "model_p": float(model_outcome.probability),
                    "market_p": float(norm.get(selection_key, 0.0)),
                    "price": float(snapshot.price_decimal),
                }
            if market_summary:
                grouped[market_name] = market_summary
        return grouped


__all__ = ["ValueService"]
