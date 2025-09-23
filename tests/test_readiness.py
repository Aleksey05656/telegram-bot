"""
@file: test_readiness.py
@description: Readiness endpoint behaviour tests.
@dependencies: app.health, app.runtime_state
@created: 2025-09-30
"""
from __future__ import annotations

import asyncio

import pytest

from app.health import HealthServer
from app.runtime_state import STATE


async def _fetch(host: str, port: int, path: str) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: test\r\n\r\n".encode()
    writer.write(request)
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return data.decode("utf-8", errors="ignore")


@pytest.mark.asyncio()
async def test_ready_endpoint_reflects_runtime_state(unused_tcp_port: int) -> None:
    server = HealthServer("127.0.0.1", unused_tcp_port)
    STATE.db_ready = False
    STATE.polling_ready = False
    STATE.scheduler_ready = False
    await server.start()
    try:
        not_ready = await _fetch("127.0.0.1", unused_tcp_port, "/ready")
        assert "503" in not_ready

        STATE.db_ready = True
        STATE.polling_ready = True
        STATE.scheduler_ready = True
        ready = await _fetch("127.0.0.1", unused_tcp_port, "/ready")
        assert "200" in ready
        assert "ready" in ready
    finally:
        STATE.db_ready = False
        STATE.polling_ready = False
        STATE.scheduler_ready = False
        await server.stop()
