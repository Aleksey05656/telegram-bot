"""
@file: test_metrics_endpoint.py
@description: Metrics endpoint smoke tests.
@dependencies: app.metrics
@created: 2025-09-30
"""
from __future__ import annotations

import socket
import time
import urllib.request

from app.metrics import start_metrics_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_metrics_endpoint_serves_prometheus_payload() -> None:
    port = _free_port()
    start_metrics_server(port)
    time.sleep(0.2)
    response = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5)
    payload = response.read().decode("utf-8")
    assert "bot_updates_total" in payload
    assert "handler_latency_seconds" in payload
