"""
/**
 * @file: app/value_calibration/backtest.py
 * @description: Backtesting utilities to calibrate value betting thresholds per league/market.
 * @dependencies: dataclasses, datetime, math, statistics, typing
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import log
from statistics import mean, pstdev
from typing import Iterable, Iterator, Sequence


@dataclass(slots=True)
class BacktestSample:
    """Single historical betting opportunity joined with realised outcome."""

    pulled_at: datetime
    kickoff_utc: datetime
    league: str
    market: str
    selection: str
    match_key: str
    price_decimal: float
    edge_pct: float
    confidence: float
    result: int


@dataclass(slots=True)
class BacktestMetrics:
    """Aggregated performance metrics for a set of samples."""

    samples: int
    wins: int
    hit_rate: float
    avg_edge_pct: float
    avg_price: float
    avg_log_gain: float
    sharpe: float


@dataclass(slots=True)
class BacktestResult:
    """Optimal calibration thresholds for league/market pair."""

    league: str
    market: str
    tau_edge: float
    gamma_conf: float
    metric: float
    metrics: BacktestMetrics


@dataclass(slots=True)
class BacktestConfig:
    """Configuration for the backtesting routine."""

    min_samples: int
    validation: str
    optim_target: str
    edge_grid: Sequence[float]
    confidence_grid: Sequence[float]
    folds: int = 4
    walk_step: int | None = None


class BacktestRunner:
    """Evaluate historical samples and identify optimal thresholds."""

    def __init__(self, samples: Sequence[BacktestSample]) -> None:
        if not samples:
            raise ValueError("BacktestRunner requires at least one sample")
        self._samples = tuple(sorted(samples, key=lambda item: item.pulled_at))

    def calibrate(self, config: BacktestConfig) -> list[BacktestResult]:
        grouped = _group_by_pair(self._samples)
        results: list[BacktestResult] = []
        for (league, market), league_samples in grouped.items():
            best = self._optimize_group(league_samples, config)
            if best:
                results.append(BacktestResult(league=league, market=market, **best))
        return results

    def _optimize_group(
        self, samples: Sequence[BacktestSample], config: BacktestConfig
    ) -> dict[str, object] | None:
        if len(samples) < config.min_samples:
            return None
        windows = list(_build_windows(samples, config))
        if not windows:
            return None
        best_metric = float("-inf")
        best_payload: dict[str, object] | None = None
        for tau in config.edge_grid:
            for gamma in config.confidence_grid:
                aggregated = _evaluate_thresholds(windows, tau, gamma)
                metric_value = _score_metric(aggregated.metrics, config.optim_target)
                if metric_value > best_metric:
                    best_metric = metric_value
                    best_payload = {
                        "tau_edge": float(tau),
                        "gamma_conf": float(gamma),
                        "metric": metric_value,
                        "metrics": aggregated.metrics,
                    }
        return best_payload


def _group_by_pair(samples: Sequence[BacktestSample]):
    grouped: dict[tuple[str, str], list[BacktestSample]] = {}
    for sample in samples:
        key = (sample.league, sample.market)
        grouped.setdefault(key, []).append(sample)
    return grouped


def _build_windows(
    samples: Sequence[BacktestSample], config: BacktestConfig
) -> Iterator[Sequence[BacktestSample]]:
    total = len(samples)
    if config.validation == "walk_forward":
        step = config.walk_step or max(total // max(config.folds, 1), 1)
        for start in range(0, total, step):
            window = samples[start : start + step]
            if window:
                yield window
    else:
        folds = max(config.folds, 1)
        fold_size = max(total // folds, 1)
        for index in range(folds):
            start = index * fold_size
            if start >= total:
                break
            end = total if index == folds - 1 else start + fold_size
            yield samples[start:end]


def build_windows(
    samples: Sequence[BacktestSample], config: BacktestConfig
) -> list[Sequence[BacktestSample]]:
    """Public helper returning windows for inspection and testing."""

    return list(_build_windows(samples, config))


@dataclass(slots=True)
class _WindowResult:
    metrics: BacktestMetrics


def _evaluate_thresholds(
    windows: Iterable[Sequence[BacktestSample]],
    tau_edge: float,
    gamma_conf: float,
) -> _WindowResult:
    picked: list[BacktestSample] = []
    for window in windows:
        for sample in window:
            if sample.edge_pct >= tau_edge and sample.confidence >= gamma_conf:
                picked.append(sample)
    metrics = _compute_metrics(picked)
    return _WindowResult(metrics=metrics)


def _compute_metrics(samples: Sequence[BacktestSample]) -> BacktestMetrics:
    if not samples:
        return BacktestMetrics(
            samples=0,
            wins=0,
            hit_rate=0.0,
            avg_edge_pct=0.0,
            avg_price=0.0,
            avg_log_gain=0.0,
            sharpe=0.0,
        )
    wins = sum(1 for item in samples if item.result)
    hit_rate = wins / len(samples)
    avg_edge = mean(item.edge_pct for item in samples)
    avg_price = mean(item.price_decimal for item in samples)
    profits: list[float] = []
    log_returns: list[float] = []
    for item in samples:
        profit = _bet_profit(item.price_decimal, item.result)
        profits.append(profit)
        log_returns.append(_safe_log_return(profit))
    avg_log_gain = mean(log_returns)
    sharpe = 0.0
    if len(profits) > 1:
        volatility = pstdev(profits)
        if volatility > 0:
            sharpe = mean(profits) / volatility
    return BacktestMetrics(
        samples=len(samples),
        wins=wins,
        hit_rate=hit_rate,
        avg_edge_pct=avg_edge,
        avg_price=avg_price,
        avg_log_gain=avg_log_gain,
        sharpe=sharpe,
    )


def _bet_profit(price: float, result: int) -> float:
    if price <= 1.0:
        return -1.0
    return result * (price - 1.0) - (1 - result)


def _safe_log_return(profit: float) -> float:
    wealth = 1.0 + profit
    if wealth <= 0:
        return log(1e-9)
    return log(wealth)


def _score_metric(metrics: BacktestMetrics, target: str) -> float:
    if metrics.samples == 0:
        return float("-inf")
    target_lower = target.lower()
    if target_lower == "sharpe":
        return metrics.sharpe
    if target_lower == "hit":
        return metrics.hit_rate
    if target_lower == "loggain":
        return metrics.avg_log_gain
    raise ValueError(f"Unknown optimisation target: {target}")


def iter_recent_samples(
    samples: Iterable[BacktestSample],
    *,
    within: timedelta,
    now: datetime,
) -> Iterator[BacktestSample]:
    boundary = now - within
    for sample in samples:
        if sample.pulled_at >= boundary:
            yield sample


__all__ = [
    "BacktestSample",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestRunner",
    "BacktestConfig",
    "build_windows",
    "iter_recent_samples",
]
