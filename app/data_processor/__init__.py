"""
@file: __init__.py
@description: Public interface for the data processor scaffolding.
@dependencies: pandas
@created: 2025-09-16

Top-level package for the upcoming data processor implementation.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .features import build_features
from .matrix import to_model_matrix
from .validate import validate_input

__all__ = ("__version__", "build_features", "to_model_matrix", "validate_input")
