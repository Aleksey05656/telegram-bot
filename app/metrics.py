"""
@file: metrics.py
@description: Prometheus metric registry and helpers.
@dependencies: prometheus_client
@created: 2025-09-30
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram, start_http_server

__all__ = [
    "bot_updates_total",
    "bot_commands_total",
    "bot_digest_sent_total",
    "retrain_success_total",
    "retrain_failure_total",
    "db_size_bytes",
    "queue_depth",
    "handler_latency",
    "render_latency_seconds",
    "value_candidates_total",
    "value_picks_total",
    "value_detector_latency_seconds",
    "value_confidence_avg",
    "value_edge_weighted_avg",
    "value_backtest_last_run_ts",
    "value_backtest_sharpe",
    "value_backtest_samples",
    "value_calibrated_pairs_total",
    "provider_reliability_score",
    "provider_fresh_share",
    "provider_latency_ms",
    "odds_anomaly_detected_total",
    "picks_settled_total",
    "portfolio_roi_rolling",
    "clv_mean_pct",
    "start_metrics_server",
    "update_db_size",
    "set_queue_depth",
    "record_command",
    "record_update",
    "record_digest_sent",
    "record_retrain_success",
    "record_retrain_failure",
    "observe_render_latency",
    "record_value_detector_latency",
    "periodic_db_size_updater",
]


bot_updates_total = Counter(
    "bot_updates_total", "Total Telegram updates handled"
)
bot_commands_total = Counter(
    "bot_commands_total", "Total bot commands handled", ["cmd"]
)
bot_digest_sent_total = Counter(
    "bot_digest_sent_total", "Total digests delivered"
)
retrain_success_total = Counter(
    "retrain_success_total", "Successful retrain runs"
)
retrain_failure_total = Counter(
    "retrain_failure_total", "Failed retrain runs"
)
db_size_bytes = Gauge("db_size_bytes", "SQLite file size in bytes")
queue_depth = Gauge("queue_depth", "Internal task queue depth")
handler_latency = Histogram(
    "handler_latency_seconds", "Bot handler latency seconds"
)
render_latency_seconds = Histogram(
    "render_latency_seconds", "Rendering latency seconds", ["cmd"]
)
value_candidates_total = Counter(
    "value_candidates_total", "Value betting candidates detected"
)
value_picks_total = Counter(
    "value_picks_total", "Value betting picks emitted"
)
value_detector_latency_seconds = Histogram(
    "value_detector_latency_seconds", "Value detector latency seconds"
)
value_confidence_avg = Gauge(
    "value_confidence_avg", "Average confidence of emitted value picks"
)
value_edge_weighted_avg = Gauge(
    "value_edge_weighted_avg", "Average weighted edge for emitted value picks"
)
value_backtest_last_run_ts = Gauge(
    "value_backtest_last_run_ts", "Unix timestamp of the last calibration backtest"
)
value_backtest_sharpe = Gauge(
    "value_backtest_sharpe", "Backtest Sharpe ratio per league/market", ["league", "market"]
)
value_backtest_samples = Gauge(
    "value_backtest_samples", "Backtest sample size per league/market", ["league", "market"]
)
value_calibrated_pairs_total = Gauge(
    "value_calibrated_pairs_total", "Total number of calibrated league/market pairs"
)

provider_reliability_score = Gauge(
    "provider_reliability_score",
    "Reliability score per provider/market/league",
    ["provider", "market", "league"],
)
provider_fresh_share = Gauge(
    "provider_fresh_share",
    "Share of fresh odds for provider",
    ["provider", "market", "league"],
)
provider_latency_ms = Gauge(
    "provider_latency_ms",
    "Average latency of odds snapshots in milliseconds",
    ["provider", "market", "league"],
)
odds_anomaly_detected_total = Counter(
    "odds_anomaly_detected_total",
    "Total anomalies detected among provider odds",
    ["provider", "market"],
)
picks_settled_total = Counter(
    "picks_settled_total",
    "Number of picks settled by outcome",
    ["outcome"],
)
portfolio_roi_rolling = Gauge(
    "portfolio_roi_rolling",
    "Rolling ROI percentage for the picks portfolio",
    ["window_days"],
)
clv_mean_pct = Gauge(
    "clv_mean_pct",
    "Mean CLV percentage across settled picks",
)


def start_metrics_server(port: int) -> None:
    """Start Prometheus HTTP server on the given port if not already running."""

    start_http_server(port)


def update_db_size(db_path: str | os.PathLike[str]) -> None:
    """Update database size gauge for the provided SQLite path."""

    try:
        size = Path(db_path).stat().st_size
    except FileNotFoundError:
        size = 0
    db_size_bytes.set(size)


def set_queue_depth(depth: int) -> None:
    """Publish queue depth gauge for background workers."""

    queue_depth.set(max(depth, 0))


def record_command(command: str) -> None:
    """Increment command counter for the provided command name."""

    if not command:
        command = "unknown"
    bot_commands_total.labels(cmd=command).inc()


def record_digest_sent() -> None:
    """Increment digest counter."""

    bot_digest_sent_total.inc()


def record_update() -> None:
    """Increment update counter."""

    bot_updates_total.inc()


def record_retrain_success() -> None:
    """Increment retrain success counter."""

    retrain_success_total.inc()


def record_retrain_failure() -> None:
    """Increment retrain failure counter."""

    retrain_failure_total.inc()


def observe_render_latency(cmd: str, duration: float) -> None:
    """Publish render latency measurement for a command."""

    render_latency_seconds.labels(cmd=cmd or "unknown").observe(duration)


def record_value_detector_latency(duration: float) -> None:
    """Publish latency measurement for the value detector pipeline."""

    value_detector_latency_seconds.observe(duration)


async def periodic_db_size_updater(
    db_path: str | os.PathLike[str],
    interval: float,
    stop_event: asyncio.Event,
) -> None:
    """Periodically update the DB size gauge until the stop event is set."""

    while not stop_event.is_set():
        update_db_size(db_path)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
