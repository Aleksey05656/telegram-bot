"""
@file: test_registry_local.py
@description: Tests for LocalModelRegistry save/load
@dependencies: app.ml.model_registry
@created: 2025-09-16
"""

from app.ml.model_registry import LocalModelRegistry


def test_local_registry_saves_and_loads(tmp_path):
    reg = LocalModelRegistry(base_dir=tmp_path)
    obj = {"value": 42}
    reg.save(obj, "base_glm", season=2025)
    loaded = reg.load("base_glm", season=2025)
    assert loaded["value"] == 42
