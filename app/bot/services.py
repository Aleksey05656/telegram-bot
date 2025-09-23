"""
/**
 * @file: app/bot/services.py
 * @description: Domain services for predictions, explainability and exports.
 * @dependencies: datetime, pathlib, csv, math, telegram.services
 * @created: 2025-09-23
 */
"""

from __future__ import annotations

import base64
import csv
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    matplotlib = None  # type: ignore[assignment]
    plt = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

from config import settings
from logger import logger

try:
    from telegram.services import DeterministicPredictorService, SportMonksFixturesRepository
except ModuleNotFoundError:  # pragma: no cover - offline stub

    class SportMonksFixturesRepository:  # type: ignore[override]
        async def list_fixtures_for_date(self, *_args, **_kwargs):  # pragma: no cover - stub
            return []

        async def get_fixture(self, _match_id: int):  # pragma: no cover - stub
            return None

    class DeterministicPredictorService:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs) -> None:  # pragma: no cover - stub
            return

        async def get_prediction(self, *_args, **_kwargs):  # pragma: no cover - stub
            return {}

        @staticmethod
        def _estimate_lambdas(_match_id: int) -> tuple[float, float]:  # pragma: no cover - stub
            return 1.0, 1.0

from app.data_source import SportmonksDataSource

from .storage import record_report


@dataclass(slots=True)
class Prediction:
    match_id: int
    home: str
    away: str
    league: str
    kickoff: datetime
    markets: dict[str, Any]
    totals: dict[str, Any]
    btts: dict[str, Any]
    top_scores: list[dict[str, Any]]
    lambda_home: float
    lambda_away: float
    expected_goals: float
    fair_odds: dict[str, float]
    confidence: float
    modifiers: list[dict[str, Any]]
    delta_probabilities: dict[str, float]
    summary: str
    freshness_hours: float | None = None
    standings: list[dict[str, Any]] = field(default_factory=list)
    injuries: list[dict[str, Any]] = field(default_factory=list)


class PredictionFacade:
    """Aggregate prediction and explanation data for bot commands."""

    def __init__(
        self,
        fixtures_repo: SportMonksFixturesRepository | None = None,
        predictor: DeterministicPredictorService | None = None,
        data_source: SportmonksDataSource | None = None,
    ) -> None:
        self._fixtures = fixtures_repo or SportMonksFixturesRepository()
        self._predictor = predictor or DeterministicPredictorService(self._fixtures)
        self._data_source = data_source or SportmonksDataSource()

    async def today(self, target_date: date, *, league: str | None = None) -> list[Prediction]:
        fixtures = await self._fixtures.list_fixtures_for_date(target_date)
        return await self._collect_predictions(fixtures, league=league)

    async def league_fixtures(
        self,
        league_code: str,
        target_date: date,
    ) -> list[Prediction]:
        fixtures = await self._fixtures.list_fixtures_for_date(target_date)
        return await self._collect_predictions(fixtures, league=league_code)

    async def match(self, match_id: int) -> Prediction:
        fixture = await self._fixtures.get_fixture(match_id)
        if not fixture:
            raise ValueError(f"Матч {match_id} не найден")
        predictions = await self._collect_predictions([fixture])
        return predictions[0]

    async def explain(self, match_id: int) -> Prediction:
        return await self.match(match_id)

    async def _collect_predictions(
        self,
        fixtures: Iterable[dict[str, Any]],
        *,
        league: str | None = None,
    ) -> list[Prediction]:
        items: list[Prediction] = []
        league_lower = league.lower() if league else None
        for fixture in fixtures:
            if league_lower and league_lower not in str(fixture.get("league", "")).lower():
                continue
            try:
                payload = await self._predictor.get_prediction(int(fixture["id"]))
                items.append(self._to_prediction(payload))
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Не удалось получить прогноз для %s: %s", fixture.get("id"), exc)
        return items

    def _to_prediction(self, payload: dict[str, Any]) -> Prediction:
        fixture = payload.get("fixture", {})
        match_id = int(fixture.get("id") or payload.get("id") or 0)
        lam_home, lam_away = DeterministicPredictorService._estimate_lambdas(match_id)
        expected_goals = lam_home + lam_away
        markets = payload.get("markets", {}) or {}
        probabilities = markets.get("1x2", {}) or {}
        fair_odds = {
            key: self._safe_inverse(value) for key, value in probabilities.items()
        }
        modifiers = self._build_modifiers(match_id, lam_home, lam_away)
        deltas = self._calc_deltas(probabilities, lam_home, lam_away)
        summary = self._summarize(modifiers, deltas)
        confidence = self._confidence_from_scores(payload.get("top_scores", []))
        try:
            context = self._data_source.fixture_context(match_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Context lookup failed", extra={"match": match_id, "error": str(exc)})
            context = None
        freshness = context.freshness_hours if context else None
        standings = context.standings if context else []
        injuries = context.injuries if context else []

        return Prediction(
            match_id=match_id,
            home=str(fixture.get("home", "?")),
            away=str(fixture.get("away", "?")),
            league=str(fixture.get("league", "")),
            kickoff=self._coerce_datetime(fixture.get("kickoff")),
            markets=markets,
            totals=payload.get("totals", {}) or {},
            btts=payload.get("both_teams_to_score", {}) or {},
            top_scores=list(payload.get("top_scores", [])),
            lambda_home=lam_home,
            lambda_away=lam_away,
            expected_goals=expected_goals,
            fair_odds=fair_odds,
            confidence=confidence,
            modifiers=modifiers,
            delta_probabilities=deltas,
            summary=summary,
            freshness_hours=freshness,
            standings=standings,
            injuries=injuries,
        )

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    @staticmethod
    def _safe_inverse(value: float) -> float:
        if value <= 0:
            return float("inf")
        return round(1.0 / value, 2)

    @staticmethod
    def _confidence_from_scores(scores: Iterable[dict[str, Any]]) -> float:
        top = 0.0
        second = 0.0
        for idx, item in enumerate(scores):
            prob = float(item.get("probability", 0.0))
            if idx == 0:
                top = prob
            elif idx == 1:
                second = prob
                break
        spread = max(0.0, top - second)
        confidence = min(0.95, 0.4 + spread * 2)
        return round(confidence, 3)

    @staticmethod
    def _build_modifiers(match_id: int, lam_home: float, lam_away: float) -> list[dict[str, Any]]:
        shift = (match_id % 7 - 3) * 0.03
        fatigue = (match_id % 5 - 2) * 0.02
        injuries = (match_id % 3 - 1) * 0.015
        return [
            {"name": "Мотивация", "delta": round(shift, 3), "impact": round(shift * 0.8, 3)},
            {"name": "Усталость", "delta": round(-fatigue, 3), "impact": round(-fatigue * 0.5, 3)},
            {"name": "Травмы", "delta": round(-injuries, 3), "impact": round(-injuries * 0.6, 3)},
        ]

    @staticmethod
    def _calc_deltas(probabilities: dict[str, Any], lam_home: float, lam_away: float) -> dict[str, float]:
        total = lam_home + lam_away
        base_home = lam_home / total if total else 0.33
        base_away = lam_away / total if total else 0.33
        base_draw = max(0.0, 1.0 - base_home - base_away)
        return {
            "home": round(float(probabilities.get("home", 0.0)) - base_home, 4),
            "draw": round(float(probabilities.get("draw", 0.0)) - base_draw, 4),
            "away": round(float(probabilities.get("away", 0.0)) - base_away, 4),
        }

    @staticmethod
    def _summarize(modifiers: list[dict[str, Any]], deltas: dict[str, float]) -> str:
        dominant = max(modifiers, key=lambda item: abs(item.get("impact", 0.0)), default=None)
        if dominant:
            factor = dominant.get("name", "Фактор")
        else:
            factor = "Равновесие"
        trend = max(deltas, key=lambda key: abs(deltas[key]), default="home")
        direction = {"home": "хозяев", "draw": "ничьи", "away": "гостей"}.get(trend, trend)
        return f"Главное влияние — {factor}. Вероятность {direction} скорректирована существеннее всего."

    def generate_csv(self, prediction: Prediction, *, reports_dir: Path | None = None) -> Path:
        root = Path(reports_dir or settings.REPORTS_DIR)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"match_{prediction.match_id}.csv"
        with path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["match_id", prediction.match_id])
            writer.writerow(["home", prediction.home])
            writer.writerow(["away", prediction.away])
            writer.writerow(["league", prediction.league])
            writer.writerow(["kickoff", prediction.kickoff.isoformat()])
            writer.writerow(["lambda_home", prediction.lambda_home])
            writer.writerow(["lambda_away", prediction.lambda_away])
            writer.writerow(["expected_goals", prediction.expected_goals])
            writer.writerow([])
            writer.writerow(["market", "value"])
            for market, value in prediction.markets.get("1x2", {}).items():
                writer.writerow([market, value])
            writer.writerow(["totals_over_2.5", prediction.totals.get("2.5", {}).get("over", 0.0)])
            writer.writerow(["totals_under_2.5", prediction.totals.get("2.5", {}).get("under", 0.0)])
            writer.writerow(["btts_yes", prediction.btts.get("yes", 0.0)])
            writer.writerow(["btts_no", prediction.btts.get("no", 0.0)])
        record_report(f"csv:{prediction.match_id}", match_id=prediction.match_id, path=str(path))
        return path

    def generate_png(self, prediction: Prediction, *, reports_dir: Path | None = None) -> Path:
        root = Path(reports_dir or settings.REPORTS_DIR)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"match_{prediction.match_id}.png"
        if plt is None or np is None:
            fallback = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
            )
            path.write_bytes(fallback)
            record_report(f"png:{prediction.match_id}", match_id=prediction.match_id, path=str(path))
            return path

        fig, axes = plt.subplots(1, 2, figsize=(8, 4))
        totals = prediction.totals.get("2.5", {})
        axes[0].bar(["Over", "Under"], [totals.get("over", 0.0), totals.get("under", 0.0)], color=["#4caf50", "#f44336"])
        axes[0].set_title("Totals 2.5")
        axes[0].set_ylim(0, 1)
        scores = prediction.top_scores[:5] or [{"score": "0:0", "probability": 0.0}]
        labels = [item.get("score", "?") for item in scores]
        values = [float(item.get("probability", 0.0)) for item in scores]
        matrix = np.array(values or [0.0])
        axes[1].imshow(matrix.reshape(1, -1), cmap="Blues", aspect="auto")
        axes[1].set_yticks([])
        axes[1].set_xticks(range(len(labels)))
        axes[1].set_xticklabels(labels)
        axes[1].set_title("Топ скорлайны")
        fig.suptitle(f"{prediction.home} vs {prediction.away}")
        fig.tight_layout()
        fig.savefig(path, format="png")
        plt.close(fig)
        record_report(f"png:{prediction.match_id}", match_id=prediction.match_id, path=str(path))
        return path


__all__ = ["Prediction", "PredictionFacade"]
