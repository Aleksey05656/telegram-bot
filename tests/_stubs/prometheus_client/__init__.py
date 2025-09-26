"""
/**
 * @file: prometheus_client/__init__.py
 * @description: Minimal in-memory Prometheus client stubs for offline metrics testing.
 * @dependencies: typing
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

__all__ = ["Counter", "Gauge", "Histogram", "start_http_server", "generate_latest"]


class _ValueHolder:
    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value = 0.0

    def inc(self, amount: float) -> None:
        self._value += amount

    def set(self, value: float) -> None:
        self._value = value

    def get(self) -> float:
        return self._value


class _CounterChild:
    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value = _ValueHolder()

    def inc(self, amount: float = 1.0) -> None:
        self._value.inc(amount)

    def clear(self) -> None:
        self._value.set(0.0)


class _GaugeChild(_CounterChild):
    def set(self, value: float) -> None:
        self._value.set(value)


class _HistogramChild(_GaugeChild):
    def observe(self, value: float) -> None:
        self._value.inc(value)


class Counter:
    """Simple counter implementation accumulating values per label set."""

    def __init__(
        self,
        _name: str,
        _documentation: str,
        labelnames: Iterable[str] | None = None,
        **_kwargs: object,
    ) -> None:
        self._value = _ValueHolder()
        self._labelnames = tuple(labelnames or ())
        self._children: Dict[Tuple[str, ...], _CounterChild] = {}

    def inc(self, amount: float = 1.0) -> None:
        self._value.inc(amount)

    def clear(self) -> None:
        self._value.set(0.0)
        self._children.clear()

    def labels(self, **labels: str) -> _CounterChild:
        key = tuple(str(labels.get(name, "")) for name in self._labelnames)
        child = self._children.get(key)
        if child is None:
            child = _CounterChild()
            self._children[key] = child
        return child


class Gauge(Counter):
    """Gauge behaves like Counter but allows explicit set operations."""

    def __init__(self, _name: str, _documentation: str, labelnames: Iterable[str] | None = None) -> None:
        super().__init__(_name, _documentation, labelnames)
        self._children = {key: _GaugeChild() for key in self._children}

    def set(self, value: float) -> None:
        self._value.set(value)

    def labels(self, **labels: str) -> _GaugeChild:  # type: ignore[override]
        key = tuple(str(labels.get(name, "")) for name in self._labelnames)
        child = self._children.get(key)
        if child is None:
            child = _GaugeChild()
            self._children[key] = child
        return child


class Histogram(Counter):
    """Simplified histogram supporting observe operations per label set."""

    def labels(self, **labels: str) -> _HistogramChild:  # type: ignore[override]
        key = tuple(str(labels.get(name, "")) for name in self._labelnames)
        child = self._children.get(key)
        if child is None:
            child = _HistogramChild()
            self._children[key] = child
        return child

    def observe(self, value: float) -> None:
        self._value.inc(value)


def start_http_server(_port: int) -> None:  # pragma: no cover - stubbed server
    return None


def generate_latest(*_args, **_kwargs) -> bytes:  # pragma: no cover - stubbed exporter
    return b""

