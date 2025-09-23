"""
/**
 * @file: pydantic_settings/__init__.py
 * @description: Lightweight stub for pydantic-settings used in offline testing.
 * @dependencies: os, pathlib
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel

__all__ = ["BaseSettings", "SettingsConfigDict"]


def SettingsConfigDict(**values: Any) -> Dict[str, Any]:
    """Return a plain dictionary mimicking pydantic SettingsConfigDict."""

    return dict(values)


class BaseSettings(BaseModel):
    """Minimal BaseSettings that pulls overrides from environment and optional .env file."""

    model_config: Dict[str, Any] = {}

    def __init__(self, **data: Any) -> None:
        merged = self._load_env()
        merged.update(data)
        super().__init__(**merged)

    @classmethod
    def _load_env(cls) -> Dict[str, Any]:
        config = getattr(cls, "model_config", {}) or {}
        env_values: Dict[str, Any] = {}
        file_values: Dict[str, str] = {}
        env_file = config.get("env_file")
        if env_file:
            path = Path(env_file)
            if path.exists():
                file_values.update(_read_env_file(path))
        annotations = getattr(cls, "__pydantic_annotations__", {})
        fields = getattr(cls, "__pydantic_fields__", {})
        for name, info in fields.items():
            alias = info.alias or name
            raw = os.getenv(alias)
            if raw is None and alias in file_values:
                raw = file_values[alias]
            if raw is None:
                continue
            env_values[name] = cls._coerce_from_env(raw, annotations.get(name))
        return env_values

    @classmethod
    def _coerce_from_env(cls, raw: str, annotation: Any) -> Any:
        if annotation in (None, Any):
            return raw
        if annotation is bool:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if annotation is int:
            try:
                return int(raw)
            except ValueError:
                return raw
        if annotation is float:
            try:
                return float(raw)
            except ValueError:
                return raw
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        if origin in (tuple, list, set):
            parts = [item.strip() for item in raw.split(",") if item.strip()]
            if origin is tuple:
                return tuple(parts)
            if origin is set:
                return set(parts)
            return parts
        return raw


def _read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values

