"""
@file: tests/diag/test_value_check.py
@description: Tests for the diagtools.value_check CLI exit codes and summary output.
@dependencies: pytest, diagtools.value_check
@created: 2025-09-23
"""

from __future__ import annotations

from datetime import UTC, datetime, date
from pathlib import Path

import pytest

from app.bot.services import Prediction
from diagtools import value_check


def _make_prediction() -> Prediction:
    kickoff = datetime(2024, 9, 1, 18, tzinfo=UTC)
    return Prediction(
        match_id=1001,
        home="Arsenal",
        away="Manchester City",
        league="EPL",
        kickoff=kickoff,
        markets={
            "1x2": {"home": 0.35, "draw": 0.30, "away": 0.35},
        },
        totals={"2.5": {"over": 0.55, "under": 0.45}},
        btts={"yes": 0.62, "no": 0.38},
        top_scores=[],
        lambda_home=1.4,
        lambda_away=1.2,
        expected_goals=2.6,
        fair_odds={"home": 2.1, "draw": 3.3, "away": 2.9},
        confidence=0.8,
        modifiers=[],
        delta_probabilities={},
        summary="",
        freshness_hours=2.0,
    )


class _StubFacade:
    def __init__(self, predictions: list[Prediction]) -> None:
        self._predictions = predictions

    async def today(
        self,
        target_date: date,
        *,
        league: str | None = None,
    ) -> list[Prediction]:  # pragma: no cover - exercised in tests
        return list(self._predictions)


@pytest.mark.parametrize(
    "provider, fixtures, expected_code",
    [
        (
            "csv",
            Path("tests/fixtures/odds/sample.csv"),
            0,
        ),
        ("dummy", None, 1),
    ],
)
def test_value_check_cli_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    fixtures: Path | None,
    expected_code: int,
) -> None:
    prediction = _make_prediction()

    class _Factory(_StubFacade):
        def __init__(self) -> None:
            super().__init__([prediction])

    monkeypatch.setattr(value_check, "PredictionFacade", _Factory)
    
    class _FixedDate(date):
        @classmethod
        def today(cls) -> "_FixedDate":  # pragma: no cover - simple override
            return cls(2024, 9, 1)

    monkeypatch.setattr(value_check, "date", _FixedDate)
    monkeypatch.setattr(value_check.settings, "ODDS_PROVIDER", provider, raising=False)
    monkeypatch.setattr(value_check.settings, "VALUE_MIN_EDGE_PCT", 3.0, raising=False)
    monkeypatch.setattr(value_check.settings, "VALUE_MIN_CONFIDENCE", 0.6, raising=False)
    monkeypatch.setattr(value_check.settings, "VALUE_MAX_PICKS", 5, raising=False)
    monkeypatch.setattr(
        value_check.settings,
        "VALUE_MARKETS",
        "1X2,OU_2_5,BTTS",
        raising=False,
    )
    monkeypatch.setattr(
        value_check.settings,
        "ODDS_OVERROUND_METHOD",
        "proportional",
        raising=False,
    )
    if fixtures is not None:
        monkeypatch.setenv("ODDS_FIXTURES_PATH", str(fixtures.resolve()))
    else:
        monkeypatch.delenv("ODDS_FIXTURES_PATH", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        value_check.main()

    assert excinfo.value.code == expected_code

