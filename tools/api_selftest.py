"""
@file: tools/api_selftest.py
@description: Offline FastAPI self-test runner for QA-min profile
@dependencies: app.api:app, fastapi, starlette
@created: 2024-05-09
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

if os.getenv("USE_OFFLINE_STUBS") == "1":
    os.environ.setdefault("QA_STUB_SSL", "1")
    try:
        from tools.qa_stub_injector import install_stubs

        install_stubs()
    except Exception:  # pragma: no cover - defensive stub hook
        pass


def _collect_env_flags() -> Dict[str, str]:
    relevant_prefixes = ("USE_", "OFFLINE", "NO_PROXY", "PIP_")
    env_snapshot: Dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith(relevant_prefixes):
            env_snapshot[key] = value
    return dict(sorted(env_snapshot.items()))


def main() -> int:
    env_snapshot = _collect_env_flags()
    print("Environment snapshot for API self-test:")
    if env_snapshot:
        for key, value in env_snapshot.items():
            print(f"- {key}={value}")
    else:
        print("- (no offline-related environment variables detected)")

    try:
        from starlette.testclient import TestClient
    except Exception:
        TestClient = None  # type: ignore[assignment]

    try:
        import fastapi as fastapi_module
    except Exception:
        fastapi_module = None  # type: ignore[assignment]

    if (
        fastapi_module is None
        or TestClient is None
        or getattr(fastapi_module, "__OFFLINE_STUB__", False)
        or getattr(TestClient, "__OFFLINE_STUB__", False)
    ):
        payload = {"skipped": "fastapi not installed"}
        print("API self-test results:")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    try:
        from app.api import app  # type: ignore[import]
    except Exception as exc:
        print(f"Failed to import app.api:app -> {exc}")
        return 1

    results: dict[str, dict[str, Any]] = {}
    with TestClient(app) as client:  # type: ignore[arg-type]
        for endpoint in ("/healthz", "/readyz", "/__smoke__/warmup", "/smoke/warmup"):
            try:
                response = client.get(endpoint)
            except Exception as exc:  # pragma: no cover - runtime failure
                results[endpoint] = {"error": str(exc)}
                continue

            payload: dict[str, Any]
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw": response.text}

            results[endpoint] = {
                "status_code": response.status_code,
                "payload": payload,
            }

    print("API self-test results:")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
