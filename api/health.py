"""
@file: api/health.py
@description: Minimal FastAPI health and readiness probes.
@dependencies: app.fastapi_compat
@created: 2025-11-07
"""

from __future__ import annotations

from typing import Any

from app.fastapi_compat import APIRouter

router = APIRouter(tags=["system"])


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, str]:
    """Return a minimal liveness payload for platform probes."""

    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
def readyz() -> dict[str, Any]:
    """Return a minimal readiness payload for platform probes."""

    return {"status": "ok", "checks": {}}


__all__ = ["router", "healthz", "readyz"]
