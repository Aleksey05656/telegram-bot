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


def test_metrics_emitted_on_prediction(monkeypatch):
    """Ensure gauges are updated even when the outcome is unknown."""
    # populate window with a known result
    record_prediction("1x2", "EPL", 0.8, 1)

    e_label = rolling_ece.labels(market="1x2", league="EPL")
    l_label = rolling_logloss.labels(market="1x2", league="EPL")
    calls = {"ece": 0, "logloss": 0}

    def fake_e_set(value):
        calls["ece"] += 1

    def fake_l_set(value):
        calls["logloss"] += 1

    monkeypatch.setattr(e_label, "set", fake_e_set)
    monkeypatch.setattr(l_label, "set", fake_l_set)

    record_prediction("1x2", "EPL", 0.6, None)

    assert calls["ece"] == 1
    assert calls["logloss"] == 1


def test_metrics_zero_without_results():
    """Metrics should be zero when no matches have been completed."""
    e_label = rolling_ece.labels(market="1x2", league="SERIEA")
    l_label = rolling_logloss.labels(market="1x2", league="SERIEA")

    record_prediction("1x2", "SERIEA", 0.5, None)

    assert e_label._value.get() == 0.0
    assert l_label._value.get() == 0.0
