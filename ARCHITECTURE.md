<!--
@file: ARCHITECTURE.md
@description: Current architecture overview
@dependencies: docs/Project.md
@created: 2025-09-10
-->

# Architecture

Updated 2025-09-10.

- **app/** – FastAPI application with configuration, middlewares and observability.
- **services/** – business logic and data processing utilities.
- **ml/** – machine learning models и `LocalModelRegistry` (артефакты в каталоге `artifacts/` или `MODEL_REGISTRY_PATH`) и prediction pipeline.
- **tests/** – unit, contract, smoke and end-to-end tests.
- SportMonks client (`app/integrations/sportmonks_client.py`) переключает заглушку через `SPORTMONKS_STUB`.
- Observability: Sentry controlled by `SENTRY_ENABLED`; Prometheus `/metrics` expose labels `service`, `env`, `version` (from `GIT_SHA` or `APP_VERSION`). Simulation reports include version info in their headers.

## λ_base → modifiers → λ_final

PredictionPipeline сначала вычисляет базовые λ, затем применяет модификаторы
и получает λ_final. На этом этапе рассчитываются метрики `glm_base_*` и
`glm_mod_final_*`, результаты сохраняются в `reports/metrics/` и логируются
с тегами `service/env/version/season/modifiers_applied` для последующего
наблюдения.

## ML stack

Core libs: numpy >=1.26,<2.0 and pandas 2.2.2.

See `docs/Project.md` for a detailed design.

## Simulation & Markets

`services/simulator.py` uses `ml/sim/bivariate_poisson.py` to generate correlated
scores. Aggregators expose markets 1x2, totals (0.5–5.5), BTTS and correct
score grid 0..6 with tail `OTHER`. The prediction pipeline calls the simulator
after computing final λ and persists markets to SQLite and Markdown report.
Parameters are configurable via `SIM_RHO`, `SIM_N`, `SIM_CHUNK`.

## Storage

`storage/persistence.py` provides `SQLitePredictionsStore` writing probabilities
to table `predictions(match_id, market, selection, prob, ts, season, extra)`
with SQLite fallback (`PREDICTIONS_DB_URL`).

## CLI retrain

`scripts/cli.py` использует `click` и объединяет подкоманды `retrain`:

- `run` — обучает GLM (через `scripts/train_glm.py`), при флаге `--with-modifiers`
  тренирует `ml/modifiers_model.py`, сохраняет артефакты в `LocalModelRegistry` и
  добавляет срез в `reports/RUN_SUMMARY.md`;
- `schedule` — прокидывает cron в `workers/runtime_scheduler.register` через
  `workers.retrain_scheduler.schedule_retrain`;
- `status` — выводит список зарегистрированных задач и счётчик `jobs_registered_total`.

Модели и отчёты CLI живут в `artifacts/<SEASON_ID>/` и `reports/metrics/`.
