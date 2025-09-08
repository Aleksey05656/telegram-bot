"""
@file: test_metrics.py
@description: Tests for rolling ECE and LogLoss calculations.
@dependencies: metrics/metrics.py
@created: 2025-08-24
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from metrics import record_prediction
from metrics.metrics import rolling_ece, rolling_logloss


def test_ece_alert(monkeypatch):
    messages = []

    def fake_capture_message(msg, level="warning"):
        messages.append((msg, level))

    monkeypatch.setattr("metrics.metrics.sentry_sdk.capture_message", fake_capture_message)

    for _ in range(200):
        record_prediction("1x2", "EPL", 0.9, 0)

    ece = rolling_ece.labels(market="1x2", league="EPL")._value.get()
    logloss = rolling_logloss.labels(market="1x2", league="EPL")._value.get()
    assert ece > 0.05
    assert logloss > 0
    assert messages and "High ECE" in messages[0][0]
