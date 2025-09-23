"""
@file: model_registry.py
@description: Simple local filesystem model registry with season support
@dependencies: joblib
@created: 2025-09-16
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib


class LocalModelRegistry:
    """Persist and load models from the filesystem."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        data_root = Path(os.getenv("DATA_ROOT", "/data"))
        default_dir = Path(os.getenv("MODEL_REGISTRY_PATH", str(data_root / "artifacts")))
        base_path = Path(base_dir) if base_dir else default_dir
        if not base_path.is_absolute():
            base_path = data_root / base_path
        self.base_dir = base_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, name: str, season: int | str | None = None) -> Path:
        subdir = str(season) if season is not None else "default"
        path = self.base_dir / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{name}.pkl"

    def save(self, model: Any, name: str, season: int | str | None = None) -> Path:
        path = self._model_path(name, season)
        joblib.dump(model, path)
        return path

    def load(self, name: str, season: int | str | None = None) -> Any:
        path = self._model_path(name, season)
        return joblib.load(path)
