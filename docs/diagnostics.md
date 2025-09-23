<!--
@file: docs/diagnostics.md
@description: Extended Diagnostics v2 guide (data quality, drift, golden, bench, chaos scenarios).
@created: 2025-10-07
-->

# Diagnostics v2 Guide

Diagnostics v2 aggregates data quality, model validation, drift detection and operational checks into a single command line entry point.

## Core commands

```bash
# Run full suite (pytest + smoke + diagnostics + gates)
python tools/run_diagnostics.py --all

# Data quality only (schema, NaN, outliers)
python tools/run_diagnostics.py --data-quality

# Golden regression baseline check / update
python tools/golden_regression.py --check
python tools/golden_regression.py --update

# Drift report against synthetic/reference window
python tools/drift_report.py --reports-dir reports/diagnostics/drift

# Benchmark bot renderers
python tools/bench.py --iterations ${BENCH_ITER}
```

## Sections overview

- **Data Quality** — contract validation via `app/data_quality` (schema, duplicates, NaN, outliers, league consistency, season overlaps).
- **Golden Baseline** — deterministic snapshot of GLM coefficients, λ-profiles and market probabilities; epsilon gates configured via `GOLDEN_*` env vars.
- **Drift Detection** — PSI/KS for feature, label and prediction distributions; artefacts in `reports/diagnostics/drift/` (summary Markdown + JSON + PNG).
- **Calibration & Coverage** — Expected Calibration Error for 1X2/OU2.5/BTTS plus Monte-Carlo interval checks (80% / 90%).
- **Bi-Poisson Invariance** — sanity checks for market swaps and top scorelines when home/away are flipped.
- **Benchmarks** — latency/memory for `/today`, `/match`, `/explain` rendering paths; default P95 budget from `BENCH_P95_BUDGET_MS`.
- **Chaos / Ops** — smoke CLI, health endpoints, runtime lock exercise and backup inventory.
- **Static Analysis & Security** — strict mypy for `app/` и `app/bot/`, `bandit`, `pip-audit` и проверка утечек секретов в логах.

## Artefacts layout

```
reports/
└── diagnostics/
    ├── data_quality/        # summary.md + per-check CSVs
    ├── drift/               # summary.md, summary.json, plots/
    ├── calibration/         # reliability_*.png + coverage info
    ├── bench/               # bench.json + summary.md
    ├── DIAGNOSTICS.md       # aggregated Markdown report
    └── diagnostics_report.json
```

## Chaos / resilience scenarios

`tools/run_diagnostics.py` exercises:

- Runtime lock acquire/release path (`app.runtime_lock`).
- Health/ready HTTP probes in stub mode.
- Recording bot payloads and keyboard layouts to ensure format stability.
- Handling fallback when reports cannot be written (logs warnings in JSON payload).

## CI integration

`docs/quality_gates.md` enumerates the stop-the-line conditions. The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. `pytest -q`
2. `python tools/run_diagnostics.py --all`
3. `python tools/golden_regression.py --check`
4. `python tools/drift_report.py --ref-days ${DRIFT_REF_DAYS}`
5. `python tools/bench.py --iterations ${BENCH_ITER}`

Failures in any gate (golden deltas, drift PSI fail, benchmark p95 above budget, ❌ data quality) break the build.
