"""/**
 * @file: db_url.py
 * @description: Utility helpers to assemble database connection URL from environment variables.
 * @dependencies: os, urllib.parse, typing
 * @created: 2025-10-02
 */
Utilities for building database connection URLs.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote_plus


def build_db_url() -> Optional[str]:
    """Return the database URL from environment variables.

    The priority is an explicitly provided ``DATABASE_URL``. If it is not set,
    the URL is composed from individual credentials: ``DB_USER``,
    ``DB_PASSWORD``, ``DB_HOST`` and ``DB_NAME``. The password is quoted using
    :func:`urllib.parse.quote_plus` to keep special characters safe for DSN
    usage.

    Returns:
        Optional[str]: A ready-to-use SQLAlchemy asyncpg DSN when enough
        information is available. ``None`` when neither ``DATABASE_URL`` nor
        the individual credentials are fully defined.
    """

    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    host = os.environ.get("DB_HOST")
    name = os.environ.get("DB_NAME")

    if not all([user, password, host, name]):
        return None

    safe_password = quote_plus(password)
    return f"postgresql+asyncpg://{user}:{safe_password}@{host}:5432/{name}"
