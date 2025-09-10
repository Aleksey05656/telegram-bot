"""
@file: verify.py
@description: Smoke runner using FastAPI TestClient
@dependencies: fastapi, app.main
@created: 2025-09-10
"""

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    if resp.status_code != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
