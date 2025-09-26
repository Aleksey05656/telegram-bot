<!--
@file: README.md
@description: Project description and quick start
@dependencies: requirements.txt, Makefile
@created: 2025-09-10
-->

# Telegram Bot

![Diagnostics v2 ✓ / CI gated](https://img.shields.io/badge/Diagnostics%20v2-%E2%9C%93%20%2F%20CI%20gated-brightgreen)
![Drift: CI-gated ✅](https://img.shields.io/badge/Drift-CI--gated%20%E2%9C%85-brightgreen)
![Value calibration gated ✓](https://img.shields.io/badge/Value%20calibration-gated%20%E2%9C%93-brightgreen)

Telegram bot that exposes a FastAPI service and ML pipeline for football match predictions.

## Observability

Sentry can be toggled via the `SENTRY_ENABLED` environment variable. Prometheus metrics are exposed when `ENABLE_METRICS=1` (default port `METRICS_PORT=8000`) and include constant labels `service`, `env` and `version` (from `GIT_SHA` or `APP_VERSION`). Markdown reports produced by simulation scripts also embed the version in the header.

## Reliability v2 badges

- `/value` и `/compare` показывают бейдж `Reliability: csv …, http …` для текущей лиги/рынка и кнопку «Почему этот провайдер?» с расшифровкой fresh/latency/stability/closing из `app.lines.reliability_v2`.
- Админ-команда `/providers [league] [market]` выводит компактную таблицу reliability v2 (score, coverage, fresh_share, latency) и подсвечивает провайдеров ниже порога `BEST_PRICE_MIN_SCORE`.
- Портфель (`/portfolio`) дополнен агрегатами по ROI/CLV, чтобы быстрее оценивать динамику сигналов.

### Diagnostics automation

- `diagtools.scheduler` выполняет ежедневный прогон диагностики (`DIAG_SCHEDULE_CRON`, `DIAG_ON_START`, `DIAG_MAX_RUNTIME_MIN`).
- После прогона генерируется HTML-дэшборд (`reports/diagnostics/site/index.html`) и обновляется история запусков (`reports/diagnostics/history/`).
- Новые метрики: `diag_runs_total{trigger=…}` и `diag_last_status{section=…}` — помогают в Grafana/Prometheus отслеживать стабильность секций.
- Админ-команды бота: `/diag`, `/diag last`, `/diag drift`, `/diag link` (результаты уходят только в чаты из `ADMIN_IDS`).
- Политика «no-binaries-in-git»: отчёты (`reports/**`), данные (`data/**`) и любые `*.png/*.parquet/*.zip/*.sqlite` не коммитятся. CI job `assert-no-binaries` падает при попытке добавить такие файлы.
- CI job `diagnostics-scheduled` публикует артефакты HTML/истории; за ревью drift-референсов отвечает `diagtools.drift_ref_update` (с флагом `AUTO_REF_UPDATE`).
- CI job `value-agg-clv-gate` прогоняет `python -m diagtools.clv_check` и падает, если средний CLV опускается ниже `CLV_FAIL_THRESHOLD_PCT`. Артефакты `reports/diagnostics/value_clv.{json,md}` прикладываются к сборке.

## Offline QA

- Job `offline-qa` в CI проверяет, что `pytest -q` успешно выполняется в окружении без тяжёлых ML-библиотек. Перед запуском тестов выполняется гард `tools/ci_assert_no_binaries.sh`.
- Лёгкие стабы находятся в `tests/_stubs/` и автоматически подключаются, если реальные пакеты (`numpy`, `pandas`, `sqlalchemy`, `joblib` и другие) не установлены.
- Для принудительного использования стабов выставьте `USE_OFFLINE_STUBS=1` (например, в CI или локально); чтобы использовать реальные зависимости, установите соответствующие пакеты и оставьте переменную пустой.
- Тесты, помеченные `@pytest.mark.needs_np`, автоматически пропускаются, если стек `numpy/pandas` недоступен.

## Reliability snapshot

- **Single instance** — `app/runtime_lock.py` предотвращает параллельные запуски (lock в `/data/runtime.lock`).
- **Graceful shutdown** — `SIGTERM`/`SIGINT` останавливают polling через `TelegramBot.stop()` с таймаутом `SHUTDOWN_TIMEOUT`.
- **Health/Readiness** — `/health` отражает сам факт работы процесса, `/ready` возвращает 200 только когда SQLite и планировщик инициализированы и polling стартовал. Проба включается `ENABLE_HEALTH=1` (порт 8080, см. `amvera.yaml`).
- **Логи** — ротация 10 МБ×5 в `/data/logs/app.log`, stdout в logfmt, JSON для файлов.
- **ENV-контракт** — `.env.example` синхронизирован с кодом (pytest `tests/test_env_contract.py`).

## Quick start

```bash
cp .env.example .env
make setup
make check
```

See [ARCHITECTURE.md](ARCHITECTURE.md) and `docs/Project.md` for more details.

## Деплой на Amvera

Полная процедура и чек-листы описаны в [docs/deploy-amvera.md](docs/deploy-amvera.md).

### Git-поток

```bash
git clone git@github.com:your-org/telegram-bot.git
cd telegram-bot
git remote add amvera ssh://git@amvera.example.com/telegram-bot.git
git push amvera main
```

### Переменные окружения

Переменные задаются в разделе «Переменные» Amvera (на сборке недоступны):

- `TELEGRAM_BOT_TOKEN` — токен из BotFather (обязательный).
- `DATABASE_URL` / `DATABASE_URL_RO` / `DATABASE_URL_R` — Postgres DSN для записи и чтения.
- `REDIS_URL` — URL управляемого Redis (опционально).
- `DB_PATH` — путь к SQLite-фолбэку (по умолчанию `/data/bot.sqlite3`).
- `MODEL_REGISTRY_PATH` — каталог артефактов моделей (по умолчанию `/data/artifacts`).
- `REPORTS_DIR` — каталог отчётов и Markdown-снимков (по умолчанию `/data/reports`).
- `LOG_DIR` — каталог JSON-логов (по умолчанию `/data/logs`).
- `STARTUP_DELAY_SEC` — задержка перед запуском long polling (секунды, защита от «double getUpdates»).
- `ENABLE_POLLING` — включение Telegram polling (установите `0` для обслуживания без бота).
- `ENABLE_SCHEDULER` — включает регистрацию задач переобучения и сервисных джоб.
- `FAILSAFE_MODE` — при `1` отключает тяжёлые задачи (retrain/maintenance) для аварийного режима.
- `ENABLE_METRICS` / `METRICS_PORT` — включение Prometheus эндпоинта и его порт (по умолчанию `8000`).
- `BACKUP_DIR` / `BACKUP_KEEP` — каталог и глубина ротации для резервных копий SQLite (`/data/backups`, `10`).
- `PYTHONUNBUFFERED=1` — отключает буферизацию stdout/stderr.
- `APP_VERSION` и `GIT_SHA` — метки релиза и коммита для логов/метрик.
- `ODDS_PROVIDERS` / `ODDS_PROVIDER_WEIGHTS` / `ODDS_PROVIDER` / `ODDS_AGG_METHOD` / `ODDS_SNAPSHOT_RETENTION_DAYS` / `ODDS_REFRESH_SEC` / `ODDS_TIMEOUT_SEC` / `ODDS_RETRY_ATTEMPTS` / `ODDS_BACKOFF_BASE` / `ODDS_RPS_LIMIT` —
  настройки мультипровайдерной агрегации и частоты обновления котировок (режимы `dummy`, `csv`, `http`).
- `ODDS_OVERROUND_METHOD` — метод нормализации маржи (`proportional` или `shin`).
- `VALUE_MIN_EDGE_PCT` / `VALUE_MIN_CONFIDENCE` / `VALUE_MAX_PICKS` / `VALUE_MARKETS` — пороги value-детектора.
- `VALUE_ALERT_MIN_EDGE_DELTA` / `VALUE_ALERT_UPDATE_DELTA` / `VALUE_ALERT_MAX_UPDATES` — антиспам правила для value-оповещений.
- `ENABLE_VALUE_FEATURES` — включает команды `/value`, `/compare`, `/alerts` и связанные оповещения.
- `ODDS_FIXTURES_PATH` (опционально) — путь до CSV-фикстур для оффлайн-провайдера.
- `CLV_WINDOW_BEFORE_KICKOFF_MIN` / `CLV_FAIL_THRESHOLD_PCT` — окно поиска closing line и порог гейта CLV для CI.

Для оффлайн-прогона value-фич установите `ENABLE_VALUE_FEATURES=1`, `ODDS_PROVIDER=csv` и
`ODDS_FIXTURES_PATH=tests/fixtures/odds`. Так `diagtools.value_check` и тесты будут работать без внешнего API.

### Хранилище

Amvera монтирует постоянный том в `/data`. Все изменяемые файлы (SQLite, отчёты, артефакты моделей, логи) сохраняются в этом каталоге, код и артефакты сборки остаются неизменными.

### Запуск и smoke

`amvera.yaml` запускает `python main.py`. Скрипт поддерживает `--dry-run` для дымового теста:

```bash
python -m main --dry-run
```

Команда выполняет инициализацию зависимостей (кэш, загрузка рейтингов) и завершает процесс без запуска long polling — используется в CI и при проверке конфигурации. Основной режим запускает Aiogram-поллинг после задержки `STARTUP_DELAY_SEC`.

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
| `/diag [last|drift|link]` | Chat-Ops для диагностики (только админы) | `/diag last` |
| `/value [league] [date] [limit]` | Топ value-кейсы за выбранный день (требует `ENABLE_VALUE_FEATURES=1`) | `/value EPL date=2024-09-01 limit=3` |
| `/compare <match>` | Сравнение наших вероятностей с консенсусными котировками и кнопкой «Провайдеры» (`ENABLE_VALUE_FEATURES=1`) | `/compare Arsenal` |
| `/portfolio` | Личная сводка CLV и последние сигналы (`ENABLE_VALUE_FEATURES=1`) | `/portfolio` |
| `/alerts [on|off] [edge=…] [league]` | Настройка персональных value-оповещений (`ENABLE_VALUE_FEATURES=1`) | `/alerts on edge=5 EPL` |

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

## SportMonks API reference

```bash
# Список матчей в окне (минимальный include)
curl "https://api.sportmonks.com/v3/football/fixtures/between/2025-09-26/2025-10-10?api_token=API_TOKEN&include=participants;scores;states&per_page=50&timezone=Europe/Berlin&locale=ru"

# Полная карточка матча для расчётов (xGFixture + lineups.xGLineup)
curl "https://api.sportmonks.com/v3/football/fixtures/123456?api_token=API_TOKEN&include=participants;scores;events;statistics;lineups.details;formations;states;lineups.xGLineup;xGFixture&timezone=Europe/Berlin&locale=ru"

# xG на уровне игроков для нескольких фикстур
curl "https://api.sportmonks.com/v3/football/expected/lineups?api_token=API_TOKEN&filters=fixtureIds:123456,789012"

# Live standings по лиге
curl "https://api.sportmonks.com/v3/football/standings/live/leagues/271?api_token=API_TOKEN&locale=ru"

# Потоки последних обновлений коэффициентов
curl "https://api.sportmonks.com/v3/football/odds/pre-match/latest?api_token=API_TOKEN"
curl "https://api.sportmonks.com/v3/football/odds/inplay/latest?api_token=API_TOKEN"
```

```bash
python scripts/run_simulation.py --season-id default --home H --away A --rho 0.1 \
    --n-sims 10000 --calibrate --write-db \
    --report-md "$REPORTS_DIR/metrics/ECE_simulation_default_H_vs_A.md"
```

## ML-ядро и инварианты

- `RecommendationEngine` получает данные через `DBRouter` и нормализует выходные словари перед возвратом (`1X2`, Totals, BTTS).
- Прогнозы симулируются детерминированно: `seed` берётся из настроек (`SIM_SEED`) и прокидывается через сервис предсказаний.
- Перед возвратом фильтруются `NaN`/отрицательные вероятности, `scoreline_topk` сортируется по убыванию.
- При сбоях воркер фиксирует статусы `queued/start/finished/failed`, что совместимо с `TaskManager` и внешним мониторингом.

## Storage

Predictions are stored via SQLite fallback (`storage/persistence.py`).
Table `predictions(match_id, market, selection, prob, ts, season, extra)`.
DB path is taken from `DB_PATH` (defaults to `/data/bot.sqlite3`).
Each pipeline run also writes a Markdown report
`$REPORTS_DIR/metrics/SIM_{SEASON}_{home}_vs_{away}.md` (defaults to `/data/reports/metrics/...`) with entropy stats.
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
`/data/artifacts`, который можно переопределить переменной окружения `MODEL_REGISTRY_PATH`.

## SportMonks stub mode

Режим заглушки включается, если установить `SPORTMONKS_STUB=1` или оставить `SPORTMONKS_API_TOKEN`
пустым/`dummy`. Для реального API необходимо задать токен и выставить `SPORTMONKS_STUB=0`. Клиент
использует асинхронные запросы с бэкоффом и лимитами RPS.

## Key environment variables

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `SPORTMONKS_API_KEY` — legacy ключ SportMonks (совместимость).
- `SPORTMONKS_API_TOKEN` — Bearer-токен SportMonks v3.
- `SPORTMONKS_BASE_URL` — базовый URL API (по умолчанию `https://api.sportmonks.com/v3/football`).
- `SPORTMONKS_TIMEOUT_SEC`, `SPORTMONKS_RETRY_ATTEMPTS`, `SPORTMONKS_BACKOFF_BASE` — параметры таймаутов и ретраев.
- `SPORTMONKS_RPS_LIMIT` — лимит запросов в секунду (token bucket).
- `SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS` — окно для инкрементальных синков (сегодня ± N дней).
- `SPORTMONKS_LEAGUES_ALLOWLIST` — разрешённые лиги через запятую.
- `SPORTMONKS_CACHE_TTL_SEC` — TTL для кэша HTTP-ответов.
- `SPORTMONKS_STUB` — `1` включает заглушечные ответы SportMonks.
- `SM_FRESHNESS_WARN_HOURS` / `SM_FRESHNESS_FAIL_HOURS` — пороги свежести для диагностики и CI-гейта.
- `SHOW_DATA_STALENESS` — при `1` бот показывает бейджи свежести данных.
- `MODEL_REGISTRY_PATH` — каталог LocalModelRegistry (по умолчанию `/data/artifacts`).
- `REPORTS_DIR` — каталог для Markdown отчётов и снимков CI (по умолчанию `/data/reports`).
- `LOG_DIR` — каталог JSON-логов приложения (по умолчанию `/data/logs`).
- `DB_PATH` — путь к SQLite-фолбэку для симуляций (по умолчанию `/data/bot.sqlite3`).
- `STARTUP_DELAY_SEC` — задержка перед запуском long polling (секунды, по умолчанию `0`).
- `ENABLE_POLLING` — включает/отключает запуск Telegram polling (`1` по умолчанию).
- `ENABLE_SCHEDULER` — включает регистрацию задач переобучения и обслуживания (`1` по умолчанию).
- `FAILSAFE_MODE` — при `1` отключает тяжёлые джобы (переобучение, обслуживание БД).
- `ENABLE_METRICS` / `METRICS_PORT` — экспонирование Prometheus-метрик (по умолчанию `0` / `8000`).
- `BACKUP_DIR` / `BACKUP_KEEP` — путь и количество резервных копий SQLite.
- `PYTHONUNBUFFERED` — установите `1`, чтобы логи писались без буферизации в контейнере.
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

Отчёт сохраняется в `$REPORTS_DIR/metrics/MODIFIERS_<SEASON>.md` (по умолчанию `/data/reports/metrics/...`).
Порог `--tol` (для logloss) и `--tol-ece` задаёт допустимое ухудшение.

## CI numeric enforcement (modifiers)

В job `numeric` выполняется CLI проверки модификаторов. Шаг завершается с ошибкой,
если `logloss` ухудшился больше `TOL_LOSS` или `ece` больше `TOL_ECE`.
Значения по умолчанию берутся из переменных окружения `TOL_LOSS` и `TOL_ECE`.

## SportMonks ETL

CLI `scripts/sm_sync.py` реализует backfill и инкрементальные синки данных:

```bash
python scripts/sm_sync.py --mode backfill --from 2024-05-01 --to 2024-05-05 --leagues EPL,LaLiga
python scripts/sm_sync.py --mode incremental --window-days ${SPORTMONKS_DEFAULT_TIMEWINDOW_DAYS}
```

Pipeline выполняет шаги fetch → validate → map → upsert → метрики. Данные записываются в
таблицы `sm_fixtures`, `sm_teams`, `sm_standings`, `sm_injuries`, а служебная информация —
в `sm_meta`, `map_teams`, `map_leagues`. Метрики Prometheus: `sm_requests_total`,
`sm_ratelimit_sleep_seconds_total`, `sm_etl_rows_upserted_total`, `sm_last_sync_timestamp`,
`sm_sync_failures_total`, `sm_freshness_hours_max`. Диагностика `diagtools.run_diagnostics`
добавляет раздел **Data Freshness**, а `workers.retrain_scheduler` пропускает переобучение,
если данные старше `SM_FRESHNESS_WARN_HOURS`/`SM_FRESHNESS_FAIL_HOURS`.


## Тесты без NumPy/Pandas (офлайн/прокси)

Если `numpy` и `pandas` недоступны (например, в офлайн окружении),
тесты, помеченные `@pytest.mark.needs_np`, будут автоматически пропущены.

## CI numeric enforcement

CI завершается с ошибкой, если любой тест с маркером `needs_np` был пропущен.
Чтобы обеспечить прохождение сборки в офлайн-режиме, заранее
подготовьте колёса в каталоге `wheels/` или настройте локальное зеркало PyPI
через `pip.conf`. При отсутствии необходимых пакетов тесты будут SKIP и CI
прервёт сборку.

## CI и отчёты

GitHub Actions запускает единый job `pipeline` со стадиями `lint → test-fast → smoke → coverage → reports → artifacts`.
На каждом шаге используются Makefile-профили:

- `make test-fast` — быстрый прогон `pytest -q -m "not slow and not e2e"`;
- `make test-smoke` — только smoke-маршруты бота (`pytest -q -m bot_smoke`);
- `make coverage-html` — полный pytest с coverage, HTML-отчётом и жёсткими порогами (`≥80%` total, `≥90%` для `workers/`, `database/`, `services/`, `core/services/`).

Coverage валидируется скриптом `python -m diagtools.coverage_enforce`, который читает `coverage.xml`, проверяет пороги (≥80% total и ≥90% для `workers/`, `database/`, `services/`, `core/services/`) и обновляет `$REPORTS_DIR/coverage_summary.json`.
Конфигурация `.coveragerc` исключает миграции, shell-скрипты, тесты, документацию и `__init__.py` без логики, чтобы в отчёт попадал только исполняемый код.
На этапе `reports` формируются артефакты `$REPORTS_DIR/bot_e2e_snapshot.md` (детерминированные ответы `/help`, `/model`, `/today`, `/match`, `/predict`) и `$REPORTS_DIR/rc_summary.json`
с полями `app_version`, `git_sha`, `tests_passed`, `coverage_total`, `coverage_critical_packages`, `docker_image_size_mb`, `timestamp_utc`.
Финальный шаг публикует артефакт **coverage-and-reports** с HTML-покрытием (`htmlcov/index.html`) и новыми отчётами.

## Tests

- Контрактный тест сверяет `.env.example` с `app.config.Settings`.
- E2E тест проверяет `PredictionPipeline` вместе с `LocalModelRegistry`.
- Smoke-тест гарантирует, что `TaskManager.cleanup` не падает без Redis.

Удобные профили:

```bash
# быстрый прогон без slow/e2e
make test-fast

# smoke-команды Telegram-бота
make test-smoke

# полный pytest с отчётом покрытия в терминале
make test-all

# генерация HTML-покрытия в htmlcov/
make coverage-html
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

Артефакты сохраняются в `/data/artifacts/<SEASON_ID>/` через `LocalModelRegistry`: `glm_home.pkl`,
`glm_away.pkl`, `model_info.json` и (при флаге `--with-modifiers`) `modifiers_model.pkl`.
Метрики `logloss`/`ece` модификаторов записываются в `$REPORTS_DIR/metrics/MODIFIERS_<SEASON>.md`,
а краткий итог добавляется в `$REPORTS_DIR/RUN_SUMMARY.md`.

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

## Deploy to Amvera

Use the provided `amvera.yaml` and `.env.amvera.example` to deploy three coordinated processes from a single repository. The `ROLE`
variable selects which entrypoint runs inside the container:

- `ROLE=api` → FastAPI service (`uvicorn app.api:app`) with `/healthz` readiness and automatic best-effort migrations.
- `ROLE=worker` → Background pipeline refresher (`python -m scripts.worker`) that updates features, simulations and prediction
  storage on a schedule.
- `ROLE=tgbot` → Telegram bot process (`python -m scripts.tg_bot`).

Create an `.env` file from `.env.amvera.example` (no secrets committed) and fill in the platform-specific credentials:

- `AMVERA`, `PYTHONUNBUFFERED`, `TZ`, `PORT`, `ENV`, `ROLE`
- SportMonks & Telegram tokens: `SPORTMONKS_TOKEN`, `TELEGRAM_BOT_TOKEN`
- PostgreSQL routing: `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST_RW`, `PGHOST_RO`, `PGHOST_RR`, `PGPORT`
- Redis connection: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`

Mount `/data` as a persistent volume (configured via `persistenceMount`) to keep caches, logs and scheduler artefacts shared across
roles.

### Readiness checks

- API: `GET /healthz` should return `{ "status": "ok" }`.
- Worker: review logs for `worker.refresh.done` markers to confirm successful pipeline iterations.
- Telegram bot: send `/start` in chat and ensure the bot responds with the onboarding flow.
