"""
@file: test_env_example_contract.py
@description: Ensure .env.example covers all Settings variables
@dependencies: app.config.Settings
@created: 2025-09-17
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings


def _settings_env_vars() -> set[str]:
    names: set[str] = set()
    for field_name, field in Settings.model_fields.items():
        alias = field.alias or field_name
        annotation = field.annotation
        if hasattr(annotation, "model_fields"):
            for sub_name, sub_field in annotation.model_fields.items():
                sub_alias = sub_field.alias or sub_name
                if sub_alias.isupper():
                    names.add(sub_alias)
                else:
                    names.add(f"{alias.upper()}__{sub_alias.upper()}")
        else:
            names.add(alias)
    return names


def test_env_example_matches_settings():
    env_path = Path(".env.example")
    text = env_path.read_text(encoding="utf-8")
    env_vars = {
        re.split("=", line, 1)[0] for line in text.splitlines() if line and not line.startswith("#")
    }
    expected = _settings_env_vars()
    missing = expected - env_vars
    assert not missing, f"Missing variables in .env.example: {missing}"
