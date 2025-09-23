"""
/**
 * @file: diagtools/bench.py
 * @description: Benchmarks for bot commands with latency/peak memory estimates.
 * @created: 2025-10-07
 */
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Dict

import tracemalloc

from config import settings

from app.bot.formatting import (
    format_explain,
    format_match_details,
    format_today_matches,
)
from app.bot.services import Prediction


@dataclass
class BenchResult:
    p50_ms: float
    p95_ms: float
    peak_memory_kb: float
    iterations: int


SampleBuilder = Callable[[], str]


def _sample_prediction() -> Prediction:
    now = datetime.now(UTC)
    return Prediction(
        match_id=1234,
        home="Diagnostics FC",
        away="Benchmark United",
        league="EPL",
        kickoff=now,
        markets={"1x2": {"home": 0.52, "draw": 0.28, "away": 0.2}},
        totals={"2.5": {"over": 0.61, "under": 0.39}},
        btts={"yes": 0.57, "no": 0.43},
        top_scores=[{"score": "2:1", "probability": 0.14}, {"score": "1:1", "probability": 0.12}],
        lambda_home=1.45,
        lambda_away=1.1,
        expected_goals=2.55,
        fair_odds={"home": 1.92, "draw": 3.6, "away": 4.8},
        confidence=0.68,
        modifiers=[{"name": "Форма", "delta": 0.04, "impact": 0.05}],
        delta_probabilities={"home": 0.03, "draw": -0.01, "away": -0.02},
        summary="Хозяева сохраняют высокое давление на чужой половине поля.",
    )


def _bench_case(iterations: int, builder: SampleBuilder) -> BenchResult:
    timings: list[float] = []
    peak_memory = 0
    for _ in range(iterations):
        tracemalloc.start()
        start = time.perf_counter()
        builder()
        elapsed = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        timings.append(elapsed * 1000)
        peak_memory = max(peak_memory, peak)
    timings.sort()
    p50 = statistics.median(timings)
    p95_index = min(len(timings) - 1, int(round(0.95 * len(timings))) - 1)
    p95 = timings[p95_index]
    return BenchResult(p50_ms=float(p50), p95_ms=float(p95), peak_memory_kb=float(peak_memory / 1024), iterations=iterations)


def run_benchmarks(iterations: int) -> Dict[str, BenchResult]:
    prediction = _sample_prediction()

    def today_builder() -> str:
        return format_today_matches(
            title="Матчи дня",
            timezone="Europe/Moscow",
            items=[
                {
                    "id": prediction.match_id,
                    "home": prediction.home,
                    "away": prediction.away,
                    "league": prediction.league,
                    "kickoff": prediction.kickoff,
                    "markets": prediction.markets,
                    "confidence": prediction.confidence,
                    "totals": prediction.totals,
                    "expected_goals": prediction.expected_goals,
                }
            ],
            page=1,
            total_pages=1,
        )

    def match_builder() -> str:
        return format_match_details(
            {
                "fixture": {
                    "id": prediction.match_id,
                    "home": prediction.home,
                    "away": prediction.away,
                    "league": prediction.league,
                    "kickoff": prediction.kickoff,
                },
                "markets": prediction.markets,
                "totals": prediction.totals,
                "both_teams_to_score": prediction.btts,
                "top_scores": prediction.top_scores,
                "fair_odds": prediction.fair_odds,
                "confidence": prediction.confidence,
            }
        )

    def explain_builder() -> str:
        return format_explain(
            {
                "fixture": {"home": prediction.home, "away": prediction.away},
                "lambda_home": prediction.lambda_home,
                "lambda_away": prediction.lambda_away,
                "modifiers": prediction.modifiers,
                "delta_probabilities": prediction.delta_probabilities,
                "confidence": prediction.confidence,
                "summary": prediction.summary,
            }
        )

    return {
        "/today": _bench_case(iterations, today_builder),
        "/match": _bench_case(iterations, match_builder),
        "/explain": _bench_case(iterations, explain_builder),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot formatting benchmarks")
    parser.add_argument("--iterations", type=int, default=int(os.getenv("BENCH_ITER", "30")))
    parser.add_argument("--reports-dir", default=str(Path(settings.REPORTS_DIR) / "diagnostics" / "bench"))
    parser.add_argument("--budget-ms", type=float, default=float(os.getenv("BENCH_P95_BUDGET_MS", "800")))
    return parser.parse_args()


def _write_reports(results: Dict[str, BenchResult], reports_dir: Path, budget_ms: float) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = reports_dir / f"bench_{timestamp}.json"
    json_payload = {
        "budget_ms": budget_ms,
        "cases": {
            name: {
                "p50_ms": result.p50_ms,
                "p95_ms": result.p95_ms,
                "peak_memory_kb": result.peak_memory_kb,
                "iterations": result.iterations,
            }
            for name, result in results.items()
        },
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_path = reports_dir / "summary.md"
    lines = ["# Benchmarks", "", "| Case | p50 (ms) | p95 (ms) | Peak memory (KB) | Status |", "| --- | --- | --- | --- | --- |"]
    for name, result in results.items():
        status = "✅" if result.p95_ms <= budget_ms else "⚠️"
        lines.append(
            f"| {name} | {result.p50_ms:.1f} | {result.p95_ms:.1f} | {result.peak_memory_kb:.1f} | {status} |"
        )
    lines.append("")

    suggestions = []
    for name, result in results.items():
        if result.p95_ms > budget_ms:
            suggestions.append(
                f"{name}: consider caching for at least 120 seconds or reducing payload size (p95={result.p95_ms:.1f}ms)."
            )
    if suggestions:
        lines.append("## Recommendations")
        lines.extend(f"- {item}" for item in suggestions)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def main() -> None:
    args = _parse_args()
    results = run_benchmarks(args.iterations)
    summary_path = _write_reports(results, Path(args.reports_dir), args.budget_ms)
    worst_status = max(("⚠️" if result.p95_ms > args.budget_ms else "✅" for result in results.values()), default="✅")
    print(json.dumps({"status": worst_status, "summary": str(summary_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
