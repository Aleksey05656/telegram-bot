"""
/**
 * @file: app/value_calibration/__init__.py
 * @description: Lazy export helpers for value backtesting and calibration services.
 * @dependencies: app.value_calibration.backtest, app.value_calibration.calibration_service
 * @created: 2025-10-05
 */
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "BacktestConfig",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestRunner",
    "BacktestSample",
    "CalibrationRecord",
    "CalibrationService",
]

_BACKTEST_EXPORTS = {
    "BacktestConfig",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestRunner",
    "BacktestSample",
}

_CALIBRATION_EXPORTS = {"CalibrationRecord", "CalibrationService"}


def __getattr__(name: str) -> Any:
    if name in _BACKTEST_EXPORTS:
        module = import_module(".backtest", __name__)
        return getattr(module, name)
    if name in _CALIBRATION_EXPORTS:
        module = import_module(".calibration_service", __name__)
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted({*globals().keys(), *_BACKTEST_EXPORTS, *_CALIBRATION_EXPORTS})
