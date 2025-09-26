"""
@file: feature_builder.py
@description: Construct predictive features and λ estimates from SportMonks fixtures and team stats.
@dependencies: typing, sportmonks.schemas
@created: 2025-09-23
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sportmonks.schemas import Fixture, TeamStats


@dataclass(slots=True)
class FeatureBundle:
    fixture_id: int
    lambda_home: float
    lambda_away: float
    adjustments: dict[str, float]
    degraded: bool
    snapshot: dict[str, Any]


class FeatureBuilder:
    """Translate raw SportMonks payloads into features used by downstream simulators."""

    def build(
        self,
        fixture: Fixture,
        *,
        home_stats: TeamStats | None = None,
        away_stats: TeamStats | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> FeatureBundle:
        context = dict(context or {})
        degraded = False
        base_home = self._base_lambda(home_stats)
        base_away = self._base_lambda(away_stats)
        if base_home is None:
            base_home = 1.15
            degraded = True
        if base_away is None:
            base_away = 1.05
            degraded = True

        adjustments: dict[str, float] = {}
        fatigue_home = self._fatigue_penalty(context.get("home_rest_days"))
        fatigue_away = self._fatigue_penalty(context.get("away_rest_days"))
        if fatigue_home:
            adjustments["fatigue_home"] = fatigue_home
            base_home *= fatigue_home
        if fatigue_away:
            adjustments["fatigue_away"] = fatigue_away
            base_away *= fatigue_away

        injuries_home = self._injury_penalty(context.get("home_key_absences"))
        injuries_away = self._injury_penalty(context.get("away_key_absences"))
        if injuries_home:
            adjustments["injuries_home"] = injuries_home
            base_home *= injuries_home
        if injuries_away:
            adjustments["injuries_away"] = injuries_away
            base_away *= injuries_away

        motivation_home = self._motivation_boost(context.get("home_motivation"))
        motivation_away = self._motivation_boost(context.get("away_motivation"))
        if motivation_home:
            adjustments["motivation_home"] = motivation_home
            base_home *= motivation_home
        if motivation_away:
            adjustments["motivation_away"] = motivation_away
            base_away *= motivation_away

        snapshot = {
            "fixture_id": fixture.id,
            "league_id": fixture.league_id,
            "season_id": fixture.season_id,
            "home_team_id": fixture.home_team_id,
            "away_team_id": fixture.away_team_id,
            "base_home": round(base_home, 4),
            "base_away": round(base_away, 4),
            "fatigue": {
                "home": fatigue_home,
                "away": fatigue_away,
            },
            "injuries": {
                "home": context.get("home_key_absences"),
                "away": context.get("away_key_absences"),
            },
            "motivation": {
                "home": context.get("home_motivation"),
                "away": context.get("away_motivation"),
            },
        }

        return FeatureBundle(
            fixture_id=fixture.id,
            lambda_home=float(base_home),
            lambda_away=float(base_away),
            adjustments=adjustments,
            degraded=degraded,
            snapshot=snapshot,
        )

    def _base_lambda(self, stats: TeamStats | None) -> float | None:
        if stats is None:
            return None
        if stats.xg is not None:
            return float(max(stats.xg, 0.2))
        if stats.shots_on_target is not None:
            return max(0.3, stats.shots_on_target * 0.2)
        if stats.shots is not None:
            return max(0.3, stats.shots * 0.12)
        return None

    def _fatigue_penalty(self, rest_days: Any) -> float | None:
        if rest_days is None:
            return None
        try:
            rest = float(rest_days)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None
        if rest >= 6:
            return 1.03
        if rest >= 4:
            return 1.0
        if rest >= 3:
            return 0.97
        return 0.92

    def _injury_penalty(self, key_absences: Any) -> float | None:
        if not key_absences:
            return None
        try:
            count = int(key_absences)
        except (TypeError, ValueError):
            return None
        return max(0.75, 1.0 - count * 0.05)

    def _motivation_boost(self, motivation: Any) -> float | None:
        if motivation is None:
            return None
        try:
            val = float(motivation)
        except (TypeError, ValueError):
            return None
        return max(0.9, min(1.1, 1.0 + val * 0.05))


feature_builder = FeatureBuilder()
