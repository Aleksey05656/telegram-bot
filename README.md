<!--
@file: README.md
@description: Project description and quick start
@dependencies: requirements.txt, Makefile
@created: 2025-09-10
-->

# Telegram Bot

Telegram bot that exposes a FastAPI service and ML pipeline for football match predictions.

## Observability

Sentry can be toggled via the `SENTRY_ENABLED` environment variable. Prometheus metrics include constant labels `service`, `env` and `version` (from `GIT_SHA` or `APP_VERSION`). Markdown reports produced by simulation scripts also embed the version in the header.

## Quick start

```bash
cp .env.example .env
make setup
make check
```

See [ARCHITECTURE.md](ARCHITECTURE.md) and `docs/Project.md` for more details.

## Команды бота и примеры

Telegram-бот регистрирует команды для быстрого доступа к ключевым сценариям:

| Команда | Назначение | Пример |
| --- | --- | --- |
| `/start` | Приветствие и главное меню | — |
| `/help` | Справка и список команд | — |
| `/model` | Текущая версия модели, источники данных и Redis | `/model` |
| `/today` | Матчи на сегодня (после 20:00 UTC — на завтра) | `/today` |
| `/match <id>` | Синхронный прогноз по идентификатору | `/match 12345` |
| `/predict <Команда 1 — Команда 2>` | Постановка задачи в очередь | `/predict Арсенал — Манчестер Сити` |
| `/terms` | Условия использования | `/terms` |

Команда `/predict` принимает названия команд через дефис (поддерживаются символы `-`, `–`, `—`).
Ответ содержит идентификатор задачи, по которому воркер отправит итоговый прогноз.

## Dependency lock (offline)

`requirements.lock` pins the exact versions used in this repository. Regenerate it offline via `make deps-lock` and install packages from local wheels with `make deps-sync`.

## ML stack

- numpy >=1.26,<2.0
- pandas ==2.2.2

## Simulation & Markets

Monte-Carlo simulator generates correlated scores via Bi-Poisson model. Supported markets:

- **1x2** – P(home win), P(draw), P(away win) with normalization to 1;
- **Totals** – thresholds 0.5–5.5 with over/under pairs;
- **BTTS** – probability both teams score;
- **Correct Score** – grid 0..6 with tail `OTHER`.

CLI example:

```bash
python scripts/run_simulation.py --season-id default --home H --away A --rho 0.1 \
    --n-sims 10000 --calibrate --write-db --report-md reports/metrics/ECE_simulation_default_H_vs_A.md
```

## ML-ядро и инварианты

- `RecommendationEngine` получает данные через `DBRouter` и нормализует выходные словари перед возвратом (`1X2`, Totals, BTTS).
- Прогнозы симулируются детерминированно: `seed` берётся из настроек (`SIM_SEED`) и прокидывается через сервис предсказаний.
- Перед возвратом фильтруются `NaN`/отрицательные вероятности, `scoreline_topk` сортируется по убыванию.
- При сбоях воркер фиксирует статусы `queued/start/finished/failed`, что совместимо с `TaskManager` и внешним мониторингом.

## Storage

Predictions are stored via SQLite fallback (`storage/persistence.py`).
Table `predictions(match_id, market, selection, prob, ts, season, extra)`.
DB path is taken from `PREDICTIONS_DB_URL` (defaults to `var/predictions.sqlite`).
Each pipeline run also writes a Markdown report
`reports/metrics/SIM_{SEASON}_{home}_vs_{away}.md` with entropy stats.
Control parameters via environment variables:

- `SIM_RHO` – correlation coefficient (default `0.1`)
- `SIM_N` – number of simulations (default `10000`)
- `SIM_CHUNK` – chunk size for vectorized draws (default `100000`)

## Services & Workers (скелеты)

Добавлены минимальные заготовки для боевого включения без падений в ограниченных окружениях:

- `services/prediction_pipeline.py` — продовый фасад предсказаний:
  - интерфейсы `Preprocessor`, `ModelRegistry`;
  - заглушечная модель, если реестр не доступен;
  - устойчив к отсутствию `numpy/pandas` (вернёт список списков).

- `workers/retrain_scheduler.py` — регистрация периодического переобучения:
  - `schedule_retrain(register, cron_expr=None, task=None)`;
  - читает `RETRAIN_CRON` из окружения (по умолчанию `0 3 * * *`);
  - ленивая подгрузка тренера для избежания тяжёлых импортов.

## Local model registry

`app/ml/model_registry.py` сохраняет модели на файловой системе. По умолчанию используется каталог
`artifacts/`, который можно переопределить переменной окружения `MODEL_REGISTRY_PATH`.

## SportMonks stub mode

Режим заглушки включается, если установить `SPORTMONKS_STUB=1` или оставить `SPORTMONKS_API_KEY`
пустым/`dummy`. Для реального API необходимо задать ключ и выставить `SPORTMONKS_STUB=0`.

## Key environment variables

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `SPORTMONKS_API_KEY` — ключ API SportMonks.
- `SPORTMONKS_STUB` — `1` включает заглушечные ответы SportMonks.
- `MODEL_REGISTRY_PATH` — каталог LocalModelRegistry (по умолчанию `artifacts/`).
- `RETRAIN_CRON` — crontab для планировщика (пусто/`off` выключает).
- `SEASON_ID` — сезон для скрипта обучения (по умолчанию `23855`).
- `SIM_RHO`, `SIM_N`, `SIM_CHUNK` — параметры симуляции (корреляция, число прогонов и размер чанка).

## Modifiers validation

CLI `scripts/validate_modifiers.py` сравнивает качество базовых λ и итоговых λ после модификаторов.

```bash
python scripts/validate_modifiers.py --season-id 23855 --input data/val.csv --alpha 0.005 --l2 1.0 --tol 0.0 --tol-ece 0.0
```

Метрики:

- `logloss` — средний отрицательный логарифм правдоподобия Пуассона;
- `ece` — калибровка по вероятности события (0–1).

Отчёт сохраняется в `reports/metrics/MODIFIERS_<SEASON>.md`.
Порог `--tol` (для logloss) и `--tol-ece` задаёт допустимое ухудшение.

## CI numeric enforcement (modifiers)

В job `numeric` выполняется CLI проверки модификаторов. Шаг завершается с ошибкой,
если `logloss` ухудшился больше `TOL_LOSS` или `ece` больше `TOL_ECE`.
Значения по умолчанию берутся из переменных окружения `TOL_LOSS` и `TOL_ECE`.


## Тесты без NumPy/Pandas (офлайн/прокси)

Если `numpy` и `pandas` недоступны (например, в офлайн окружении),
тесты, помеченные `@pytest.mark.needs_np`, будут автоматически пропущены.

## CI numeric enforcement

CI завершается с ошибкой, если любой тест с маркером `needs_np` был пропущен.
Чтобы обеспечить прохождение сборки в офлайн-режиме, заранее
подготовьте колёса в каталоге `wheels/` или настройте локальное зеркало PyPI
через `pip.conf`. При отсутствии необходимых пакетов тесты будут SKIP и CI
прервёт сборку.

## Coverage artifacts в CI

Job `numeric` дополнительно запускает `pytest --cov=app/data_processor` с HTML-отчётом.
После завершения пайплайна скачайте артефакт **metrics-and-artifacts** и откройте
`htmlcov/index.html` для просмотра детального покрытия. В том же архиве сохраняются
`reports/metrics/*.md` и база `var/predictions.sqlite`.

## Tests

- Контрактный тест сверяет `.env.example` с `app.config.Settings`.
- E2E тест проверяет `PredictionPipeline` вместе с `LocalModelRegistry`.
- Smoke-тест гарантирует, что `TaskManager.cleanup` не падает без Redis.

Быстрая проверка:
```bash
pytest -q -k test_services_workers_minimal
```

> Тесты помечены `@pytest.mark.needs_np`: при недоступном численном стеке будут SKIP.

## Retrain scheduler (feature-flag)

Встроена «лёгкая» интеграция планировщика:

- **ENV-флаг**: `RETRAIN_CRON`
  - пусто / `off` / `disabled` / `none` / `false` → **планировщик выключен**;
  - любое корректное выражение crontab → регистрируется задача переобучения.
- **Адаптер**: in-memory `workers/runtime_scheduler.py` (для smoke/локалки).
- **Эндпоинт**: `GET /__smoke__/retrain` — статус регистрации: enabled/count/crons.

Быстрая проверка:
```bash
RETRAIN_CRON="*/15 * * * *" uvicorn app.main:app --reload &
curl -s http://127.0.0.1:8000/__smoke__/retrain
```

Тест:
```bash
pytest -q -k test_retrain_registration
```

## CLI retrain

Командный интерфейс `python scripts/cli.py retrain ...` управляет локальным переобучением.

```bash
# Обучение базовых GLM и модификаторов с записью отчёта
python scripts/cli.py retrain run --season-id default --alpha 0.005 --l2 1.0 --with-modifiers

# Регистрация задачи в in-memory планировщике
python scripts/cli.py retrain schedule --cron "0 4 * * *"

# Диагностика зарегистрированных задач
python scripts/cli.py retrain status
```

Артефакты сохраняются в `artifacts/<SEASON_ID>/` через `LocalModelRegistry`: `glm_home.pkl`,
`glm_away.pkl`, `model_info.json` и (при флаге `--with-modifiers`) `modifiers_model.pkl`.
Метрики `logloss`/`ece` модификаторов записываются в `reports/metrics/MODIFIERS_<SEASON>.md`,
а краткий итог добавляется в `reports/RUN_SUMMARY.md`.

## Smart pre-commit fallback

Если обычный `pre-commit` упирается в прокси/GitHub (например, `CONNECT tunnel failed, response 403`),
запустите:
```bash
make pre-commit-smart
```
Цель сначала пробует обычный конфиг (онлайн), а при сетевой ошибке автоматически переключается на
локальный `.pre-commit-config.offline.yaml` (без внешних загрузок). Кеш хуков находится в `$(PRE_COMMIT_HOME)`
и по умолчанию — `.cache/pre-commit`.
В офлайн-конфигурации Ruff выполняется как `ruff check --fix`, а форматирование исходников обеспечивает `black`.

Точно так же можно запускать на части файлов:
```bash
PRECOMMIT=pre-commit PRE_COMMIT_HOME=.cache/pre-commit python scripts/run_precommit.py run --files path/to/file.py README.md
```
