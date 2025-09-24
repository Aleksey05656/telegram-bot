"""
/**
 * @file: app/lines/anomaly.py
 * @description: Odds anomaly detection using z-scores and quantile thresholds.
 * @dependencies: math, statistics, app.lines.providers.base, app.metrics
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Sequence

from app.lines.providers.base import OddsSnapshot
from app.metrics import odds_anomaly_detected_total


class OddsAnomalyDetector:
    """Detect and filter anomalous odds quotes among peers."""

    def __init__(self, *, z_max: float, quantile: float = 0.1) -> None:
        if not 0.0 < quantile < 0.5:
            raise ValueError("quantile must be between 0 and 0.5")
        self._z_max = float(z_max)
        self._quantile = float(quantile)

    def filter_anomalies(
        self, quotes: Sequence[OddsSnapshot], *, emit_metrics: bool = True
    ) -> set[str]:
        """Return providers flagged as anomalies among the provided quotes."""

        if len(quotes) < 3:
            return set()
        prices = [float(quote.price_decimal) for quote in quotes]
        if not prices:
            return set()
        avg = mean(prices)
        std = pstdev(prices) if len(prices) > 1 else 0.0
        sorted_prices = sorted(prices)
        lower = self._quantile_value(sorted_prices, self._quantile)
        upper = self._quantile_value(sorted_prices, 1.0 - self._quantile)
        flagged: set[str] = set()
        for quote in quotes:
            value = float(quote.price_decimal)
            z_score = abs(value - avg) / std if std > 0 else 0.0
            if z_score > self._z_max or value < lower or value > upper:
                flagged.add(quote.provider.lower())
                if emit_metrics:
                    odds_anomaly_detected_total.labels(
                        provider=quote.provider.lower(), market=quote.market.upper()
                    ).inc()
        return flagged

    @staticmethod
    def _quantile_value(sorted_values: Sequence[float], q: float) -> float:
        if not sorted_values:
            return 0.0
        if q <= 0:
            return float(sorted_values[0])
        if q >= 1:
            return float(sorted_values[-1])
        pos = (len(sorted_values) - 1) * q
        lower = math.floor(pos)
        upper = math.ceil(pos)
        if lower == upper:
            return float(sorted_values[int(pos)])
        lower_value = float(sorted_values[lower])
        upper_value = float(sorted_values[upper])
        weight = pos - lower
        return lower_value + (upper_value - lower_value) * weight


__all__ = ["OddsAnomalyDetector"]

