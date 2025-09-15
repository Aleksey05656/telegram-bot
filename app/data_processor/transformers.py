"""
@file: transformers.py
@description: Transformer builders for preprocessing pipelines.
@dependencies: data_processor.make_transformers
@created: 2025-09-10
"""
from __future__ import annotations

from typing import Any

try:
    from data_processor import make_transformers as _impl  # type: ignore
except Exception:
    _impl = None


def make_transformers(*args, **kwargs) -> Any:
    if _impl:
        return _impl(*args, **kwargs)

    class _Identity:
        def fit(self, X, y=None):
            return self

        def transform(self, X):
            return X

    return _Identity()