"""
@file: __init__.py
@description: Sportmonks data provider package export shortcuts.
@dependencies: none
"""

from __future__ import annotations

from .client import SportmonksClient, SportmonksClientConfig
from .provider import SportmonksProvider

__all__ = ["SportmonksClient", "SportmonksClientConfig", "SportmonksProvider"]
