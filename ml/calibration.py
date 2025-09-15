"""
@file: calibration.py
@description: Калибровка вероятностей (Platt/Isotonic).
@dependencies: numpy, sklearn
@created: 2025-08-23
"""
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


class ProbabilityCalibrator:
    def __init__(
        self,
        method: str = "platt",
        keys: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        strict_guard: bool = True,
        max_shift: float = 0.25,
        max_weight_on_large_shift: float = 0.5,
    ) -> None:
        self.method = method
        self.keys = keys or []
        self.weights = weights or {}
        self.strict_guard = bool(strict_guard)
        self.max_shift = float(max(0.0, max_shift))
        self.max_weight_on_large_shift = float(min(1.0, max(0.0, max_weight_on_large_shift)))
        self._models: Dict[str, Any] = {}

    def fit(self, p_base: Dict[str, np.ndarray], y_true: np.ndarray) -> "ProbabilityCalibrator":
        for key, p in p_base.items():
            if self.method == "isotonic":
                m = IsotonicRegression(out_of_bounds="clip")
                self._models[key] = m.fit(p, (y_true == (key)).astype(float))
            else:
                m = LogisticRegression(max_iter=1000)
                self._models[key] = m.fit(p.reshape(-1, 1), (y_true == (key)).astype(int))
        return self

    def predict(self, probs: Dict[str, float]) -> Dict[str, float]:
        calibrated: Dict[str, float] = {}
        iter_keys = list(self.keys) if self.keys else list(probs.keys())
        for k in iter_keys:
            if k not in probs:
                continue
            original_p = float(probs[k])
            m = self._models.get(k)
            cal_p = original_p
            if m is not None:
                try:
                    if hasattr(m, "predict_proba"):
                        proba = m.predict_proba([[original_p]])
                        cal_p = float(proba[0][1])
                    elif hasattr(m, "predict"):
                        y = m.predict([[original_p]])
                        cal_p = float(y[0]) if hasattr(y, "__len__") else float(y)
                    elif hasattr(m, "transform"):
                        y = m.transform([[original_p]])
                        cal_p = float(y[0][0])
                except Exception:
                    cal_p = original_p
            cal_p = max(0.0, min(1.0, cal_p))
            w = float(self.weights.get(k, 1.0))
            if w < 0.0:
                w = 0.0
            elif w > 1.0:
                w = 1.0
            if self.strict_guard and abs(cal_p - original_p) > self.max_shift:
                w = min(w, self.max_weight_on_large_shift)
            final_p = w * cal_p + (1.0 - w) * original_p
            calibrated[k] = float(max(0.0, min(1.0, final_p)))
        if self.keys:
            for k, p in probs.items():
                if k not in calibrated:
                    calibrated[k] = float(max(0.0, min(1.0, p)))
            for k in self.keys:
                if k not in calibrated:
                    calibrated[k] = float(max(0.0, min(1.0, float(probs.get(k, 0.0)))))
        if not calibrated:
            if self.keys:
                for k in self.keys:
                    calibrated[k] = 0.0
            else:
                for k, p in probs.items():
                    calibrated[k] = float(max(0.0, min(1.0, float(p))))
        s = sum(calibrated.values())
        if s <= 0:
            return {k: 0.0 for k in calibrated}
        return {k: (v / s) for k, v in calibrated.items()}


def calibrate_probs(y_true: np.ndarray, p_pred: np.ndarray) -> IsotonicRegression:
    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(p_pred, y_true)
    return ir


def apply_calibration(ir: IsotonicRegression, p: np.ndarray) -> np.ndarray:
    if ir is None:
        return np.clip(p, 1e-6, 1 - 1e-6)
    calibrated_probs = ir.predict(p)
    return np.clip(calibrated_probs, 1e-6, 1 - 1e-6)
