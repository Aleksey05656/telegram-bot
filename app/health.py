# @file: health.py
# @description: Lightweight /health TCP server.
# @dependencies: logger.py
"""Minimal asynchronous health endpoint server."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from logger import logger


@dataclass(slots=True)
class HealthServer:
    """Simple HTTP health endpoint served over asyncio."""

    host: str = "0.0.0.0"
    port: int = 8080
    _server: Optional[asyncio.base_events.Server] = None
    _task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self._task = asyncio.create_task(self._server.serve_forever())
        logger.info("Health server started on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        logger.info("Health server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            data = await reader.read(1024)
            request_line = data.splitlines()[0].decode("utf-8", errors="ignore") if data else ""
            status_line = "HTTP/1.1 200 OK\r\n"
            body = b"{\"status\":\"ok\"}"
            if not request_line.startswith("GET ") or " HTTP/" not in request_line:
                status_line = "HTTP/1.1 405 Method Not Allowed\r\n"
                body = b"{\"status\":\"method_not_allowed\"}"
            else:
                path = request_line.split(" ")[1]
                if path != "/health":
                    status_line = "HTTP/1.1 404 Not Found\r\n"
                    body = b"{\"status\":\"not_found\"}"
            headers = (
                status_line
                + "Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n"
                + "Connection: close\r\n\r\n"
            )
            writer.write(headers.encode("utf-8") + body)
            await writer.drain()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Health probe handler error: %s", exc)
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


__all__ = ["HealthServer"]
