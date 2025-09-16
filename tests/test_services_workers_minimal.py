"""
@file: test_services_workers_minimal.py
@description: Tests for minimal services and worker skeletons.
@dependencies: pytest, pandas, numpy
@created: 2025-09-12
"""
import pytest

# Mark the file as requiring numerical stack; will SKIP if numpy/pandas unavailable
pytestmark = pytest.mark.needs_np


def test_services_prediction_pipeline_stub():
    try:
        import numpy as np  # noqa: F401
        import pandas as pd
    except Exception:
        pytest.skip("numerical stack unavailable")

    from services.prediction_pipeline import PredictionPipeline

    class _Preproc:
        def transform(self, df: "pd.DataFrame") -> "pd.DataFrame":
            return df

    class _Registry:
        class _M:
            def predict_proba(self, X):
                import numpy as np

                return np.full((len(X), 2), 0.5)

        def load(self, name: str, season: int | None = None):
            return self._M()

    df = pd.DataFrame(
        {
            "home_team": ["A"],
            "away_team": ["B"],
            "date": [pd.Timestamp("2024-01-01")],
            "xG_home": [1.0],
            "xG_away": [0.8],
            "goals_home": [1],
            "goals_away": [0],
        }
    )
    pipe = PredictionPipeline(preprocessor=_Preproc(), model_registry=_Registry())
    out = pipe.predict_proba(df)
    assert getattr(out, "shape", None) == (1, 2)


def test_workers_retrain_scheduler_register_called(monkeypatch):
    calls = {}

    def _register(cron, fn):
        calls["cron"] = cron
        calls["fn"] = fn

    from workers.retrain_scheduler import schedule_retrain

    used = schedule_retrain(_register, cron_expr="0 4 * * *")
    assert used == "0 4 * * *"
    assert "cron" in calls
    assert "fn" in calls
    # ensure callable
    calls["fn"]()
