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
- **Backtest & Calibration** — подбор `τ/γ` per лига/рынок на исторических снапшотах (валидация `time_kfold`|`walk_forward`, метрики `Sharpe`, `log_gain`, `samples`, гейты `GATES_VALUE_SHARPE_*`, `BACKTEST_MIN_SAMPLES`). Результаты сохраняются в `value_calibration` и отчётах `value_calibration.{json,md}`; `python -m diagtools.value_check` по умолчанию читает последний отчёт, а флаг `--calibrate` принудительно перезапускает бэктест (используется в CI-гейте).
- **Odds Aggregation & CLV** — мультипровайдерный консенсус (best/median/weighted), тренды closing line и сводка CLV из `picks_ledger`. CLI `python -m diagtools.clv_check` публикует `value_clv.{json,md}` и возвращает ненулевой код при отсутствии записей или просадке ниже `CLV_FAIL_THRESHOLD_PCT`.
- **Bi-Poisson Invariance** — sanity checks for market swaps and top scorelines when home/away are flipped.
- **Benchmarks** — latency/memory for `/today`, `/match`, `/explain` rendering paths; default P95 budget from `BENCH_P95_BUDGET_MS`.
- **Chaos / Ops** — smoke CLI, health endpoints, runtime lock exercise and backup inventory.
- **Static Analysis & Security** — strict mypy for `app/` и `app/bot/`, `bandit`, `pip-audit` и проверка утечек секретов в логах.

## SportMonks data freshness

- ETL запускается через `scripts/sm_sync.py` (режимы `backfill` и `incremental`). В проде включайте live-синк только после
  проверки лимитов: `SPORTMONKS_RPS_LIMIT`, `SPORTMONKS_TIMEOUT_SEC`, `SPORTMONKS_RETRY_ATTEMPTS`, `SPORTMONKS_BACKOFF_BASE`.
- В `app/data_providers/sportmonks/metrics.py` публикуются метрики `sm_requests_total`, `sm_ratelimit_sleep_seconds_total`,
  `sm_etl_rows_upserted_total`, `sm_last_sync_timestamp`, `sm_sync_failures_total`, `sm_freshness_hours_max`.
- Диагностика `diag-run` добавляет раздел **Data Freshness** — статус OK/WARN/FAIL вычисляется по `SM_FRESHNESS_WARN_HOURS` и
  `SM_FRESHNESS_FAIL_HOURS`, а Markdown/JSON-отчёты включают таблицу свежести по лигам. Метрика `sm_freshness_hours_max`
  отражает максимальную задержку по таблицам `sm_*`.
- При ошибках 429/5xx включается экспоненциальный бэкофф, токен-бакет и повторные попытки (`SportmonksClient`).
- Бот показывает бейджи свежести (`SHOW_DATA_STALENESS=1`), а планировщик retrain пропускает запуск при устаревших данных.
- Для одиночной проверки без полного `diag-run` используйте `python -m diagtools.freshness --check` — CLI возвращает exit code 2
  при FAIL и печатает подробности (опционально `--json`).

## Continuous monitoring & Chat-Ops

- Планировщик (`diagtools.scheduler`) регистрируется через `workers.runtime_scheduler.register` и по умолчанию срабатывает ежедневно в `06:00` (`DIAG_SCHEDULE_CRON=0 6 * * *`).
- `DIAG_ON_START=1` запускает диагностику при старте приложения (в отдельном потоке, чтобы не блокировать бот).
- `DIAG_MAX_RUNTIME_MIN` ограничивает бюджет времени для батча команд (`diag-run`, `diag-drift`, `golden_regression --check`, `bench`).
- Итоги фиксируются в `reports/diagnostics/site/index.html` и истории `reports/diagnostics/history/*` (JSONL + CSV, ротация `DIAG_HISTORY_KEEP`).
- Алерты включаются флагом `ALERTS_ENABLED=1`; `ALERTS_CHAT_ID` — телеграм-чат админов, `ALERTS_MIN_LEVEL=WARN|FAIL` определяет порог уведомлений. Секреты автоматически маскируются по шаблону `*_TOKEN|*_KEY|PASSWORD`.
- Chat-Ops: `/diag` (ручной прогон), `/diag last` (последняя запись истории), `/diag drift` (только drift), `/diag link` (текущий HTML-дэшборд). Все команды доступны только администраторам (`ADMIN_IDS`).

HTML-дэшборд содержит статусные чипы, список секций и ссылки на `DIAGNOSTICS.md`/`diagnostics_report.json`. SVG-график по статусам хранится рядом и попадает в CI-артефакты, но не в Git. При необходимости формат можно переключить через `REPORTS_IMG_FORMAT=svg|png`.

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
    ├── history/             # history.jsonl + history.csv (runtime artefacts)
    ├── calibration/         # reliability_*.png + coverage info
    ├── value_calibration.md
    ├── value_calibration.json
    ├── value_clv.md
    ├── value_clv.json
    ├── bench/               # bench.json + summary.md
    ├── site/                # index.html + status.svg (dashboard)
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
7. Job `value-calibration-gate` запускает `python -m diagtools.value_check --calibrate --days ${BACKTEST_DAYS}` и публикует `reports/diagnostics/value_calibration.{json,md}`. Падение происходит при `Sharpe < GATES_VALUE_SHARPE_FAIL` или `samples < BACKTEST_MIN_SAMPLES`.
8. Job `value-agg-clv-gate` прогоняет `python -m diagtools.clv_check --db-path ${DB_PATH}` и выкладывает `reports/diagnostics/value_clv.{json,md}`. Exit-коды 1/2 фиксируют отсутствие записей или средний CLV ниже `CLV_FAIL_THRESHOLD_PCT`.
9. Новый job `diagnostics-scheduled` симулирует плановый запуск (cron/manual) и выкладывает артефакты `reports/diagnostics/site/**` и `reports/diagnostics/history/**`.
10. `assert-no-binaries` (первая стадия пайплайна) проверяет дифф на отсутствие бинарных файлов (`*.png`, `*.zip`, `*.sqlite` и т.д.) и мгновенно падает при нарушении политики.

Failures in any gate (golden deltas, drift PSI fail, benchmark p95 above budget, ❌ data quality) break the build.
