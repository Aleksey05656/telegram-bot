"""
@file: metrics.py
@description: Prometheus metrics and rolling ECE/LogLoss calculations.
@dependencies: prometheus_client, sentry_sdk
@created: 2025-08-24
"""

from collections import deque

from app.config import get_settings

try:
    import sentry_sdk  # type: ignore
except Exception:  # pragma: no cover

    class _SentryStub:
        @staticmethod
        def capture_message(*args, **kwargs):
            pass

    sentry_sdk = _SentryStub()

try:
    from prometheus_client import Counter, Gauge, Histogram
except Exception:  # pragma: no cover

    class _DummyMetric:
        def __init__(self, *args, **kwargs):
            self.value = 0.0

        def labels(self, **kwargs):  # type: ignore
            return self

        def inc(self, amount=1):  # type: ignore
            self.value += amount

        def observe(self, value):  # type: ignore
            self.value = value

        def set(self, value):  # type: ignore
            self.value = value

        @property
        def _value(self):  # type: ignore
            class _Val:
                def __init__(self, parent):
                    self.parent = parent

                def get(self):
                    return self.parent.value

            return _Val(self)

    Counter = Gauge = Histogram = _DummyMetric

_s = get_settings()
_version = _s.git_sha or _s.app_version
_LABELS = {"service": _s.app_name, "env": _s.env, "version": _version}

WINDOW_SIZE = 200

pred_total = Counter(
    "pred_total",
    "Total predictions",
    ["market", "league", "service", "env", "version"],
)
prob_bins = Histogram(
    "prob_bins",
    "Prediction probability distribution",
    ["market", "league", "service", "env", "version"],
    buckets=[i / 10 for i in range(11)],
)
rolling_ece = Gauge(
    "rolling_ece",
    "Rolling Expected Calibration Error",
    ["market", "league", "service", "env", "version"],
)
rolling_logloss = Gauge(
    "rolling_logloss",
    "Rolling LogLoss",
    ["market", "league", "service", "env", "version"],
)

_windows: dict[tuple[str, str], deque[tuple[float, int]]] = {}


def _get_window(key: tuple[str, str]) -> deque[tuple[float, int]]:
    window = _windows.get(key)
    if window is None:
        window = deque(maxlen=WINDOW_SIZE)
        _windows[key] = window
    return window


def _calc_ece(items: deque[tuple[float, int]]) -> float:
    n_bins = 10
    bin_totals = [0] * n_bins
    bin_correct = [0] * n_bins
    for prob, label in items:
        idx = min(int(prob * n_bins), n_bins - 1)
        bin_totals[idx] += 1
        bin_correct[idx] += label
    total = len(items)
    ece = 0.0
    for i in range(n_bins):
        if bin_totals[i] == 0:
            continue
        avg_conf = (i + 0.5) / n_bins
        acc = bin_correct[i] / bin_totals[i]
        ece += abs(acc - avg_conf) * bin_totals[i] / total
    return ece


def _calc_logloss(items: deque[tuple[float, int]]) -> float:
    import math

    eps = 1e-15
    total = 0.0
    for prob, label in items:
        p = min(max(prob, eps), 1 - eps)
        total += -(label * math.log(p) + (1 - label) * math.log(1 - p))
    return total / len(items)


def record_prediction(market: str, league: str, y_prob: float, y_true: int | None) -> None:
    """Record prediction and update rolling metrics."""
    labels = {"market": market, "league": league, **_LABELS}
    pred_total.labels(**labels).inc()
    prob_bins.labels(**labels).observe(y_prob)
    if y_true is None:
        return

    window = _get_window((market, league))
    window.append((y_prob, y_true))

    ece = _calc_ece(window)
    logloss = _calc_logloss(window)
    rolling_ece.labels(**labels).set(ece)
    rolling_logloss.labels(**labels).set(logloss)
    if ece > 0.05:
        sentry_sdk.capture_message(f"High ECE {ece:.3f} for {market}:{league}", level="warning")


def logloss_poisson(y_true: list[int], y_pred: list[float]) -> float:
    """Negative log-likelihood for Poisson predictions."""
    import math

    import numpy as np

    losses = [
        lam - y * math.log(max(lam, 1e-15)) + math.lgamma(y + 1)
        for y, lam in zip(y_true, y_pred, strict=False)
    ]
    return float(np.mean(losses))


def ece_poisson(y_true: list[int], y_pred: list[float], n_bins: int = 10) -> float:
    """Expected calibration error for Poisson predictions."""
    import math

    def _pmf(y: int, lam: float) -> float:
        return math.exp(-lam) * lam**y / math.factorial(y)

    probs = [_pmf(y, lam) for y, lam in zip(y_true, y_pred, strict=False)]
    bin_totals = [0] * n_bins
    bin_probs = [0.0] * n_bins
    for p in probs:
        idx = min(int(p * n_bins), n_bins - 1)
        bin_totals[idx] += 1
        bin_probs[idx] += p
    total = len(probs)
    ece = 0.0
    for i in range(n_bins):
        if bin_totals[i] == 0:
            continue
        avg_conf = (i + 0.5) / n_bins
        acc = bin_probs[i] / bin_totals[i]
        ece += abs(acc - avg_conf) * bin_totals[i] / total
    return ece


_METRIC_STORE: dict[str, float] = {}


def record_metrics(name: str, value: float, tags: dict[str, str]) -> None:
    """Record arbitrary metric with tags."""
    from logger import logger

    _METRIC_STORE[name] = value
    logger.info("metric=%s value=%f tags=%s", name, value, tags)


def get_recorded_metrics() -> dict[str, float]:
    """Return snapshot of recorded metrics (for testing)."""
    return _METRIC_STORE.copy()
