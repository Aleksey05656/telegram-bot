"""
@file: test_pipeline_writes_markets.py
@description: Integration test verifying PredictionPipeline writes simulated markets.
@dependencies: pandas, services/prediction_pipeline, sqlite3
@created: 2025-09-15
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from app.config import reset_settings_cache
from services.prediction_pipeline import PredictionPipeline


@pytest.mark.needs_np
def test_pipeline_writes_markets(tmp_path, monkeypatch):
    class _Pre:
        def transform(self, df: pd.DataFrame) -> pd.DataFrame:  # noqa: D401
            return df[[]]

    monkeypatch.setenv("PREDICTIONS_DB_URL", str(tmp_path / "pred.sqlite"))
    monkeypatch.setenv("SIM_N", "512")
    reset_settings_cache()

    df = pd.DataFrame(
        {
            "home": ["H"],
            "away": ["A"],
            "season": ["S"],
            "date": [pd.Timestamp("2024-01-01")],
        }
    )

    pipe = PredictionPipeline(_Pre())
    pipe.predict_proba(df)

    conn = sqlite3.connect(tmp_path / "pred.sqlite")
    rows = conn.execute("SELECT market, selection, prob FROM predictions").fetchall()
    conn.close()
    assert any(m == "1x2" for m, _, _ in rows)
    assert any(m.startswith("totals_") for m, _, _ in rows)
    assert any(m == "btts" for m, _, _ in rows)
    assert any(m == "cs" for m, _, _ in rows)

    sum_1x2 = sum(prob for m, _, prob in rows if m == "1x2")
    assert pytest.approx(1.0, rel=1e-2) == sum_1x2

    totals = {}
    for m, sel, prob in rows:
        if m.startswith("totals_"):
            thr = m.split("_", 1)[1]
            totals.setdefault(thr, {}).update({sel: prob})
    for sp in totals.values():
        assert pytest.approx(1.0, rel=1e-2) == sp.get("over", 0) + sp.get("under", 0)

    sum_cs = sum(prob for m, _, prob in rows if m == "cs")
    assert pytest.approx(1.0, rel=1e-2) == sum_cs

    report = Path("reports/metrics/SIM_S_H_vs_A.md")
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "### Entropy" in content
