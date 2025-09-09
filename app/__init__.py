"""
@file: __init__.py
@description: app package init
@dependencies: config
@created: 2025-09-09
"""

from .config import Settings, get_settings

__all__ = ["get_settings", "Settings"]
