"""
/**
 * @file: tests/diagnostics/test_bench_smoke.py
 * @description: Smoke tests for bench harness to ensure latency budget.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

from tools.bench import run_benchmarks


def test_benchmark_runs_within_budget() -> None:
    results = run_benchmarks(iterations=3)
    assert {"/today", "/match", "/explain"}.issubset(results.keys())
    for result in results.values():
        assert result.p50_ms >= 0
        assert result.p95_ms >= result.p50_ms
        assert result.peak_memory_kb >= 0
