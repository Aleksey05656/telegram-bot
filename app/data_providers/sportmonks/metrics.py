"""
@file: metrics.py
@description: Prometheus metrics for Sportmonks ETL pipeline.
@dependencies: prometheus_client
"""

from __future__ import annotations

from datetime import datetime, timezone

from prometheus_client import Counter, Gauge

sm_requests_total = Counter(
    "sm_requests_total",
    "Total Sportmonks API requests",
    ["endpoint", "status"],
)

sm_ratelimit_sleep_seconds_total = Counter(
    "sm_ratelimit_sleep_seconds_total",
    "Total seconds spent sleeping for Sportmonks rate limiting",
)

sm_etl_rows_upserted_total = Counter(
    "sm_etl_rows_upserted_total",
    "Rows upserted into Sportmonks tables",
    ["table"],
)

sm_last_sync_timestamp = Gauge(
    "sm_last_sync_timestamp",
    "Timestamp of the last successful Sportmonks sync",
    ["mode"],
)

sm_sync_failures_total = Counter(
    "sm_sync_failures_total",
    "Total Sportmonks sync failures",
    ["mode"],
)

sm_freshness_hours_max = Gauge(
    "sm_freshness_hours_max",
    "Maximum data staleness in hours across Sportmonks domains",
)


def update_last_sync(mode: str, when: datetime | None = None) -> None:
    ts = when or datetime.now(tz=timezone.utc)
    sm_last_sync_timestamp.labels(mode=mode).set(ts.timestamp())
