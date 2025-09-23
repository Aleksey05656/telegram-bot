"""
/**
 * @file: app/data_quality/contracts.py
 * @description: Declarative description of match-level dataset contracts and validation helpers.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class FieldSpec:
    """Description of a single tabular column constraint."""

    name: str
    dtype: str
    nullable: bool = False


@dataclass(frozen=True)
class MatchContract:
    """Contract describing minimal expectations for match-level feeds."""

    fields: tuple[FieldSpec, ...]
    timezone_whitelist: tuple[str, ...]
    kickoff_field: str = "kickoff_utc"
    season_start_field: str = "season_start"
    season_end_field: str = "season_end"

    def validate_schema(self, df: pd.DataFrame) -> list[str]:
        """Validate required columns and basic typing constraints."""

        messages: list[str] = []
        for field in self.fields:
            if field.name not in df.columns:
                messages.append(f"missing column: {field.name}")
                continue
            series = df[field.name]
            if not field.nullable and series.isna().any():
                messages.append(f"non-nullable column {field.name} contains missing values")
            inferred = str(series.dtype)
            if field.dtype == "datetime64[ns]":
                if not pd.api.types.is_datetime64_any_dtype(series):
                    try:
                        pd.to_datetime(series, utc=True)
                    except Exception as exc:  # pragma: no cover - defensive
                        messages.append(f"column {field.name} is not datetime convertible: {exc}")
            elif field.dtype == "string":
                if not pd.api.types.is_string_dtype(series):
                    messages.append(f"column {field.name} is expected to be string-like, got {inferred}")
            elif field.dtype == "float":
                if not pd.api.types.is_float_dtype(series) and not pd.api.types.is_integer_dtype(series):
                    messages.append(f"column {field.name} is expected numeric, got {inferred}")
            elif field.dtype == "int":
                if not pd.api.types.is_integer_dtype(series):
                    messages.append(f"column {field.name} is expected integer, got {inferred}")
        return messages

    def normalize_kickoff(self, df: pd.DataFrame) -> pd.Series:
        series = df[self.kickoff_field]
        if not pd.api.types.is_datetime64_any_dtype(series):
            normalized = pd.to_datetime(series, utc=True, errors="coerce")
        else:
            normalized = series.dt.tz_localize(UTC) if series.dt.tz is None else series.dt.tz_convert(UTC)
        return normalized

    def iterate_timezones(self, df: pd.DataFrame) -> Iterable[str]:
        for column in ("home_timezone", "away_timezone"):
            if column in df.columns:
                yield from df[column].dropna().astype(str)


_DEFAULT_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("match_id", "int"),
    FieldSpec("home_team", "string"),
    FieldSpec("away_team", "string"),
    FieldSpec("home_team_code", "string"),
    FieldSpec("away_team_code", "string"),
    FieldSpec("league", "string"),
    FieldSpec("league_code", "string"),
    FieldSpec("season", "string"),
    FieldSpec("season_start", "int"),
    FieldSpec("season_end", "int"),
    FieldSpec("kickoff_utc", "datetime64[ns]"),
    FieldSpec("home_xg", "float", nullable=False),
    FieldSpec("away_xg", "float", nullable=False),
    FieldSpec("home_xga", "float", nullable=False),
    FieldSpec("away_xga", "float", nullable=False),
)

_DEFAULT_TIMEZONES: tuple[str, ...] = (
    "UTC",
    "Europe/London",
    "Europe/Moscow",
    "Europe/Berlin",
    "America/New_York",
    "Asia/Singapore",
)


def default_match_contract() -> MatchContract:
    return MatchContract(fields=_DEFAULT_FIELDS, timezone_whitelist=_DEFAULT_TIMEZONES)
