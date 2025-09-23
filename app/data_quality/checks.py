"""
/**
 * @file: app/data_quality/checks.py
 * @description: Library of granular data quality checks used by diagnostics suite.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import pandas as pd

from .contracts import MatchContract
from .runner import DataQualityIssue


def _issue(name: str, status: str, summary: str, frame: pd.DataFrame | None = None) -> DataQualityIssue:
    if frame is not None and not frame.empty:
        frame = frame.copy()
    else:
        frame = None
    return DataQualityIssue(name=name, status=status, summary=summary, violations=frame)


def schema_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    messages = contract.validate_schema(df)
    status = "✅" if not messages else "❌"
    violations = None
    if messages:
        violations = pd.DataFrame({"issue": messages})
    summary = "schema validated" if not messages else "; ".join(messages)
    return _issue("schema", status, summary, violations)


def match_key_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    required = ["home_team", "away_team", contract.kickoff_field]
    if not all(col in df.columns for col in required):
        return _issue(
            "match_keys",
            "⚠️",
            f"columns missing for key check: {sorted(set(required) - set(df.columns))}",
        )
    key_frame = df[required].astype(str)
    duplicates = df[key_frame.duplicated(keep=False)]
    self_play = df[df["home_team"] == df["away_team"]]
    merged = pd.concat([duplicates.assign(reason="duplicate"), self_play.assign(reason="self_play")], ignore_index=True)
    status = "✅" if merged.empty else "❌"
    summary = "match keys unique" if merged.empty else f"violations={len(merged)}"
    return _issue("match_keys", status, summary, merged)


def missing_values_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    counts = df.isna().sum()
    violations = counts[counts > 0]
    if violations.empty:
        return _issue("missing_values", "✅", "no missing values detected")
    frame = violations.reset_index()
    frame.columns = ["column", "missing"]
    summary = ", ".join(f"{row.column}={row.missing}" for row in frame.itertuples())
    return _issue("missing_values", "❌", summary, frame)


def negative_expected_goals_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    columns = ["home_xg", "away_xg", "home_xga", "away_xga"]
    present = [col for col in columns if col in df.columns]
    if not present:
        return _issue("negative_xg", "⚠️", "xG columns missing")
    mask = (df[present] < 0).any(axis=1)
    bad = df.loc[mask, [contract.kickoff_field] + present]
    status = "✅" if bad.empty else "❌"
    summary = "no negative xG/xGA" if bad.empty else f"rows={len(bad)}"
    return _issue("negative_xg", status, summary, bad)


def outlier_percentile_check(df: pd.DataFrame, contract: MatchContract, *, lower: float = 0.01, upper: float = 0.99) -> DataQualityIssue:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return _issue("outliers", "⚠️", "no numeric columns")
    flagged_rows = set()
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        q_low, q_high = series.quantile([lower, upper])
        mask = (df[col] < q_low) | (df[col] > q_high)
        idx = df.index[mask].tolist()
        flagged_rows.update(idx)
    if not flagged_rows:
        return _issue("outliers", "✅", "no percentile outliers")
    subset = df.loc[sorted(flagged_rows), numeric_cols]
    details = subset.assign(_row=subset.index)
    summary = f"rows={len(details)} outside percentile bounds"
    return _issue("outliers", "⚠️", summary, details)


def league_consistency_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    required = ["league", "league_code", "home_team_code", "away_team_code"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return _issue("league_consistency", "⚠️", f"missing columns {missing}")
    mapping = df.groupby("league_code")["league"].nunique()
    inconsistent_leagues = mapping[mapping > 1]
    team_cross = []
    for col in ("home_team_code", "away_team_code"):
        league_by_team = df.groupby(col)["league_code"].nunique()
        for team, count in league_by_team.items():
            if count > 1:
                team_cross.append({"team_code": team, "league_variants": int(count)})
    if inconsistent_leagues.empty and not team_cross:
        return _issue("league_consistency", "✅", "league codes consistent")
    frame = pd.DataFrame(team_cross or [])
    notes = []
    if not inconsistent_leagues.empty:
        inconsistent_df = inconsistent_leagues.reset_index()
        inconsistent_df.columns = ["league_code", "league_count"]
        frame = pd.concat([frame, inconsistent_df], ignore_index=True, sort=False)
        notes.append(f"league_code variants: {len(inconsistent_leagues)}")
    if team_cross:
        notes.append(f"team league overlaps: {len(team_cross)}")
    return _issue("league_consistency", "⚠️", "; ".join(notes), frame if not frame.empty else None)


def season_overlap_check(df: pd.DataFrame, contract: MatchContract) -> DataQualityIssue:
    required = [contract.season_start_field, contract.season_end_field, "league_code"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return _issue("season_overlap", "⚠️", f"missing columns {missing}")
    start = contract.season_start_field
    end = contract.season_end_field
    bad_ranges: list[dict[str, int]] = []
    for league, group in df.groupby("league_code"):
        spans = group[[start, end]].drop_duplicates()
        spans = spans.sort_values(start)
        previous_end: int | None = None
        for row in spans.itertuples(index=False):
            span_start = int(getattr(row, start))
            span_end = int(getattr(row, end))
            if span_start > span_end:
                bad_ranges.append({
                    "league_code": league,
                    "season_start": span_start,
                    "season_end": span_end,
                    "reason": "start>end",
                })
                continue
            if previous_end is not None and span_start <= previous_end:
                bad_ranges.append({"league_code": league, "season_start": span_start, "season_end": span_end, "reason": "overlap"})
            previous_end = max(previous_end or span_end, span_end)
    if not bad_ranges:
        return _issue("season_overlap", "✅", "season ranges clean")
    frame = pd.DataFrame(bad_ranges)
    return _issue("season_overlap", "⚠️", f"issues={len(frame)}", frame)
