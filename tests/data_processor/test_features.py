"""
@file: test_features.py
@description: Tests for feature engineering utilities of the data processor package.
@dependencies: pandas, pytest
@created: 2025-09-16
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.data_processor.feature_engineering import build_features as legacy_build_features
from app.data_processor.features import build_features
from app.data_processor.io import load_data, save_data
from app.data_processor.transformers import make_transformers


def _sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team_id": ["A", "B", "A", "A", "B"],
            "match_date": pd.to_datetime(
                [
                    "2024-08-05",
                    "2024-08-02",
                    "2024-08-01",
                    "2024-08-03",
                    "2024-08-04",
                ]
            ),
            "goals_for": [2, 1, 0, 1, 3],
            "goals_against": [2, 1, 1, 0, 0],
            "shots": [7, 8, 5, 6, 0],
            "xg": [1.7, 0.9, 0.3, 0.8, 1.2],
        }
    )


def test_build_features_long_format_match_data() -> None:
    df = pd.DataFrame(
        {
            "home_team": ["A", "C", "A"],
            "away_team": ["B", "A", "C"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-20"]),
            "xG_home": [1.2, 1.0, 1.4],
            "xG_away": [0.8, 0.9, 0.7],
            "goals_home": [2, 1, 3],
            "goals_away": [1, 0, 1],
        }
    )

    features = build_features(df, windows=(2,))

    assert len(features) == len(df) * 2
    expected_cols = {"team_id", "opponent_id", "is_home", "rest_days", "target", "rolling_xg_for_2"}
    assert expected_cols.issubset(features.columns)
    assert features.groupby("match_id").size().eq(2).all()

    team_a = features[features["team_id"] == "A"].reset_index(drop=True)
    assert team_a["is_home"].tolist() == [1, 0, 1]
    assert team_a["target"].tolist() == [2.0, 0.0, 3.0]
    assert team_a["rest_days"].tolist() == [0, 7, 12]
    assert pytest.approx(team_a.loc[1, "rolling_xg_for_2"], rel=1e-6) == 1.2
    assert pytest.approx(team_a.loc[2, "rolling_xg_for_2"], rel=1e-6) == 1.05


def test_build_features_generates_expected_rolling_means_and_ratios() -> None:
    df = _sample_dataframe()

    engineered = build_features(
        df,
        group_key="team_id",
        sort_key="match_date",
        windows=(2, 3),
        ratio_pairs=[("goals_for", "shots")],
    )

    engineered = engineered.sort_values(["team_id", "match_date"]).reset_index(drop=True)
    team_a = engineered[engineered["team_id"] == "A"].reset_index(drop=True)
    team_b = engineered[engineered["team_id"] == "B"].reset_index(drop=True)

    assert pytest.approx(team_a.loc[1, "goals_for_rolling_mean_2"], rel=1e-6) == 0.5
    assert pytest.approx(team_a.loc[2, "goals_for_rolling_mean_2"], rel=1e-6) == 1.5
    assert pytest.approx(team_a.loc[2, "goals_against_rolling_mean_3"], rel=1e-6) == 1.0
    assert pytest.approx(team_a.loc[0, "goals_for_per_shots"], rel=1e-6) == 0.0
    assert pytest.approx(team_b.loc[0, "goals_for_per_shots"], rel=1e-6) == 0.125
    assert pd.isna(team_b.loc[1, "goals_for_per_shots"])


def test_build_features_rejects_empty_dataframe() -> None:
    df = pd.DataFrame(columns=["team_id", "match_date", "goals_for"])

    with pytest.raises(ValueError, match="Cannot build features from an empty dataframe"):
        build_features(df)


def test_build_features_requires_positive_windows() -> None:
    df = _sample_dataframe()

    with pytest.raises(ValueError, match="Rolling window must be a positive integer"):
        build_features(df, group_key="team_id", sort_key="match_date", windows=(3, 0))


def test_build_features_requires_numeric_columns() -> None:
    df = pd.DataFrame(
        {"team_id": ["A"], "match_date": pd.to_datetime(["2024-08-01"]), "label": ["x"]}
    )

    with pytest.raises(ValueError, match="No numeric columns available"):
        build_features(df, group_key="team_id", sort_key="match_date", windows=(2,))


def test_build_features_missing_ratio_column() -> None:
    df = _sample_dataframe()

    with pytest.raises(KeyError, match="ratio column 'missing/denominator'"):
        build_features(
            df, group_key="team_id", sort_key="match_date", ratio_pairs=[("missing", "denominator")]
        )


def test_build_features_rejects_non_numeric_ratio_denominator() -> None:
    df = _sample_dataframe()
    df["shots"] = ["seven", "eight", "five", "six", "zero"]

    with pytest.raises(TypeError, match="Denominator column 'shots' must be numeric"):
        build_features(
            df, group_key="team_id", sort_key="match_date", ratio_pairs=[("goals_for", "shots")]
        )


def test_legacy_feature_engineering_fallback_returns_copy() -> None:
    df = _sample_dataframe()

    legacy = legacy_build_features(df)

    assert legacy.equals(df)
    assert legacy is not df


def test_io_roundtrip(tmp_path: Path) -> None:
    df = _sample_dataframe()[["team_id", "goals_for"]].reset_index(drop=True)
    target = tmp_path / "data.csv"

    save_data(df, target.as_posix())
    loaded = load_data(target.as_posix())

    pd.testing.assert_frame_equal(loaded, df)


def test_make_transformers_identity() -> None:
    transformer = make_transformers()
    fitted = transformer.fit([[1], [2]])

    assert fitted is transformer
    assert transformer.transform([[1], [2]]) == [[1], [2]]
