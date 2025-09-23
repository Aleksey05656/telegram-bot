<!--
@file: docs/quality_gates.md
@description: Overview of Diagnostics v2 quality gates and thresholds for CI enforcement.
@created: 2025-10-07
-->

# Diagnostics v2 Quality Gates

| Section | Check | Threshold / Condition | Notes |
| --- | --- | --- | --- |
| Data Quality | Schema, duplicates, missing values, outliers | ❌ if any blocker (schema / duplicates / NaN) | CSV artefacts under `reports/diagnostics/data_quality/`. |
| Golden Baseline | GLM coefficients / λ / market probabilities | `GOLDEN_COEF_EPS` (default 0.005), `GOLDEN_LAMBDA_MAPE` (0.015), `GOLDEN_PROB_EPS` (0.005) | Recomputed via `python -m diagtools.golden_regression --check`. |
| Drift | Feature PSI + KS p-value по global/league/season | Warning ≥ `DRIFT_PSI_WARN` (0.1) или `p ≤ DRIFT_KS_P_WARN` (0.05), Fail ≥ `DRIFT_PSI_FAIL` (0.25) или `p ≤ DRIFT_KS_P_FAIL` (0.01) | `diag-drift` сохраняет Markdown/JSON/CSV, plots и reference parquet. |
| Calibration | Expected Calibration Error / coverage | ECE reported; coverage must stay within ±2 п.п. from targets (80%/90%) | Reliability PNGs stored in `reports/diagnostics/calibration/`. |
| Bi-Poisson Invariance | Market swap / scoreline symmetry | Max delta ≤ 1e-6 | Runs on mean λ from synthetic dataset. |
| Benchmarks | `/today`, `/match`, `/explain` p95 latency | P95 ≤ `BENCH_P95_BUDGET_MS` (default 800 ms) | Peak memory reported per case. |
| Smoke / Ops | CLI smoke & health checks | Exit code 0 | Uses stub mode (no external IO). |
| Static Analysis | `mypy`, `bandit`, `pip-audit`, secrets scan | ❌ on any failure/leak | Logs stored under `reports/diagnostics/static/`. |

## Updating the golden baseline

1. Run `python -m diagtools.golden_regression --update --reports-dir <reports>` locally.
2. Commit the updated `reports/golden/baseline.json` (do not change tolerances without a review).
3. Verify CI with `python -m diagtools.golden_regression --check` to ensure tolerances still hold.

## Where to inspect artefacts

| Artefact | Location |
| --- | --- |
| Data quality summary | `reports/diagnostics/data_quality/summary.md` |
| Drift summary | `reports/diagnostics/drift/drift_summary.md` + `drift_summary.json` + CSV |
| Calibration plots | `reports/diagnostics/calibration/*.png` |
| Bench metrics | `reports/diagnostics/bench/bench.json` + `summary.md` |

## Interpreting FAIL gates

- **Golden** — Adjust model pipeline or re-baseline only when modelling changes are intentional.
- **Drift** — Investigate feature pipelines / new data feeds; PSI ≥ fail threshold blocks deploy.
- **Benchmarks** — Optimise hot paths or raise cache TTLs; CI fails if p95 exceeds the configured budget.
- **Data Quality** — Blockers are immediate fixers (duplicates, schema violations, NaN critical fields).

## Drift reference updates & automation guardrails

- Для подготовки нового эталона используйте `python -m diagtools.drift_ref_update --reports-dir <dir> --tag <YYYYMMDD>`.
- Скрипт копирует `reports/diagnostics/drift/reference/*` в таймстампнутую подпапку и генерирует `changelog_<tag>.md` со сводкой окон/количеств.
- Защита от случайного запуска включена переменной `AUTO_REF_UPDATE` (`off` по умолчанию). Авто-режим возможен только при `AUTO_REF_UPDATE=approved` или передаче `--force`.
- В Git не попадают бинарные эталоны (Parquet/PNG) — они публикуются как артефакты CI и доступны через job `diagnostics-scheduled`.
