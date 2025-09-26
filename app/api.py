"""
@file: app/api.py
@description: ASGI application for Amvera deployment with health check
@dependencies: app/main.py, fastapi, uvicorn
@created: 2025-10-27
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from .main import app as main_app

api = FastAPI()


@api.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


api.mount("/", main_app)

# expose ASGI application
app = api


def _resolve_port() -> int:
    raw_port = os.getenv("PORT", "80")
    try:
        return int(raw_port)
    except (TypeError, ValueError):
        return 80


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=_resolve_port(), reload=False)


if __name__ == "__main__":
    main()
