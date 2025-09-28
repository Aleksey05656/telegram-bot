"""
@file: verify.py
@description: Smoke runner using FastAPI TestClient
@dependencies: fastapi, app.api
@created: 2025-09-10
"""

from scripts._optional import optional_dependency

TestClient = optional_dependency("fastapi.testclient", attr="TestClient")

from app.api import app


def main() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    if resp.status_code != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
