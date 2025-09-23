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
diag-run --all

# Data quality only (schema, NaN, outliers)
diag-run --data-quality

# Golden regression baseline check / update
python -m diagtools.golden_regression --check
python -m diagtools.golden_regression --update

# Drift report against synthetic/reference window
diag-drift --reports-dir reports/diagnostics/drift

# Benchmark bot renderers
python -m diagtools.bench --iterations ${BENCH_ITER}
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

## Drift v2.1

`diag-drift` реализует стратифицированный PSI/KS и CI-гейт для скоупов `global`, `league`, `season`.

### Ключевые возможности

- **Скользящие окна**: параметр `--ref-days` (якорный эталон) и `--ref-rolling-days` (предыдущий срез). При указании обоих формируются две витрины и сравнительная сводка.
- **Произвольный референс**: `--ref-path` принимает CSV/Parquet и имеет приоритет над расчётом по дням. Можно сохранять эталон в `reports/diagnostics/drift/reference/` и переиспользовать.
- **Стратификация**: метрики считаются глобально, по лигам (`league`) и сезонам (`season`).
- **Пороги**: `DRIFT_PSI_WARN/FAIL`, `DRIFT_KS_P_WARN/FAIL` (аналогичные CLI флаги) переводят скоупы в `OK/WARN/FAIL`. `FAIL` возвращает ненулевой exit code и валит CI.
- **Артефакты**: генерируются `drift_summary.md`, `drift_summary.json`, CSV по каждому скоупу, `plots/*.png` для топ-5 фич и `reference/*.parquet` + `.sha256` + `meta.json` с диапазонами дат и размером окна.

### Примеры запуска

```bash
# Быстрый прогон с дефолтами и артефактами в каталоге по умолчанию
diag-drift

# Отдельный отчёт с кастомным окном и уже собранным эталоном
diag-drift --reports-dir reports/diagnostics/drift \
           --ref-days 120 \
           --ref-rolling-days 45 \
           --ref-path reports/diagnostics/drift/reference/anchor.parquet
```

### Интерпретация статусов

- `OK` — все фичи в пределах `PSI < DRIFT_PSI_WARN` и `p-value > DRIFT_KS_P_WARN`.
- `WARN` — пересекается только уровень предупреждения. Стоит проверить артефакты и утвердить/обновить эталон.
- `FAIL` — достигнут `PSI >= DRIFT_PSI_FAIL` или `p-value <= DRIFT_KS_P_FAIL`. Скрипт завершается с кодом `1`, CI job `diagnostics-drift` краснеет.

Артефакт `reference/meta.json` фиксирует диапазон дат и количество записей для каждого окна. Чтобы обновить эталон, достаточно удалить соответствующий `.parquet` и повторно запустить `diag-drift` с нужными параметрами либо указать `--ref-path` на новый срез.

## Artefacts layout

```
reports/
└── diagnostics/
    ├── data_quality/        # summary.md + per-check CSVs
    ├── drift/               # drift_summary.md/json, *.csv, plots/, reference/
    ├── calibration/         # reliability_*.png + coverage info
    ├── bench/               # bench.json + summary.md
    ├── DIAGNOSTICS.md       # aggregated Markdown report
    └── diagnostics_report.json
```

## Chaos / resilience scenarios

`diagtools.run_diagnostics` exercises:

- Runtime lock acquire/release path (`app.runtime_lock`).
- Health/ready HTTP probes in stub mode.
- Recording bot payloads and keyboard layouts to ensure format stability.
- Handling fallback when reports cannot be written (logs warnings in JSON payload).

## CI integration

`docs/quality_gates.md` enumerates the stop-the-line conditions. The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. `pytest -q`
2. `diag-run --all`
3. `python -m diagtools.golden_regression --check`
4. `diag-drift --ref-days ${DRIFT_REF_DAYS} --ref-rolling-days ${DRIFT_ROLLING_DAYS}`
5. `python -m diagtools.bench --iterations ${BENCH_ITER}`
6. Дополнительный job `diagnostics-drift` в CI повторно запускает `diag-drift` и публикует `reports/diagnostics/drift` как артефакт.

Failures in any gate (golden deltas, drift PSI fail, benchmark p95 above budget, ❌ data quality) break the build.
