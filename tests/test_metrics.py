"""
@file: test_metrics.py
@description: Tests for rolling ECE and LogLoss calculations.
@dependencies: metrics/metrics.py
@created: 2025-08-24
"""

import os
import sys

import pytest

pytestmark = pytest.mark.needs_np

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from metrics import record_prediction  # noqa: E402
from metrics.metrics import _LABELS, rolling_ece, rolling_logloss  # noqa: E402


def test_ece_alert(monkeypatch):
    messages = []

    def fake_capture_message(msg, level="warning"):
        messages.append((msg, level))

    monkeypatch.setattr("metrics.metrics.sentry_sdk.capture_message", fake_capture_message)

    for _ in range(200):
        record_prediction("1x2", "EPL", 0.9, 0)

    labels = {"market": "1x2", "league": "EPL", **_LABELS}
    ece = rolling_ece.labels(**labels)._value.get()
    logloss = rolling_logloss.labels(**labels)._value.get()
    assert ece > 0.05
    assert logloss > 0
    assert messages
    assert "High ECE" in messages[0][0]
