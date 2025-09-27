## [2025-11-26] - Migration comment syntax cleanup
### Добавлено
- —

### Изменено
- Приведено описание миграции `20241005_004_value_v1_4` к валидному Python-docstring без изменения логики.

### Исправлено
- Исправлен синтаксис комментариев в файле миграции, устранив C-стиль и потенциальные ошибки парсинга.

## [2025-11-24] - Canary rollout support
### Добавлено
- Флаг окружения `CANARY` в конфиге, эндпоинт `/__smoke__/warmup` и таргет `make warmup` для прогрева.
- Разделы README с инструкциями по канареечной раскатке и шагами `api-canary`, CI-шаг `canary-smoke`.
### Изменено
- `/`, `/healthz`, `/readyz` теперь возвращают `canary: true` при `CANARY=1`, логи и метрики получают fallback-метку `env=canary`.
- Основной процесс и prediction worker пропускают фоновые задачи/запуск в канарейке, диагностика ограничивает алерты админ-чатами.
### Исправлено
- —

## [2025-10-30] - Monitoring alerts and runbook
### Добавлено
- Файл `monitoring/alerts.yaml` с правилами Data Freshness, ETL Failures, Worker Deadman, Odds Pipeline и API Readiness.
- Пример окружения `.env.alerts.example` с порогами без секретов.
- Runbook `docs/runbook.md` с действиями по алёртам.

### Изменено
- README дополнен разделом «Monitoring & Alerts», Makefile включает цель `alerts-validate`, CI добавляет мягкую проверку алёртов.

### Исправлено
- —

## [2025-10-29] - Amvera preflight gate
### Добавлено
- Скрипт `scripts/preflight.py` с режимами `strict` и `health` для миграций и health-check перед стартом ролей.
- Юнит-тесты `tests/scripts/test_preflight.py`, проверяющие последовательность вызовов и обработку ошибок.

### Изменено
- `amvera.yaml` условно запускает `python -m scripts.preflight --mode strict` для ролей `api` и `worker`, если `PRESTART_PREFLIGHT=1`.
- README описывает флаг `PRESTART_PREFLIGHT` и его поведение при деплое на Amvera.

### Исправлено
- Усилен фейловер старта ролей: ошибки preflight теперь прерывают запуск контейнера до инициализации процесса.

## [2025-10-28] - Amvera health/readiness unification
### Добавлено
- FastAPI эндпоинты `/healthz` и `/readyz` с проверками PostgreSQL, Redis и статусов планировщика/бота, а также промышленные тесты на алиасы.
- В `app/config.Settings` добавлены fallback-поля для PostgreSQL/Redis и предупреждения о депрекации `SPORTMONKS_TOKEN`/`SPORTMONKS_API_KEY`.

### Изменено
- `app/api.py`, smoke-тесты и `scripts/verify.py` используют `app.api:app`, обновлены проверки метрик и readiness.
- `.env.example`, `README.md` и `docs/deploy-amvera.md` отражают новые приоритеты переменных окружения и единый `/metrics` на API-порту.

### Исправлено
- Смоук-сценарии повторно загружают `app.api`, чтобы учесть флаги окружения `RETRAIN_CRON` и `ENABLE_METRICS`.
- Offline QA режим больше не пропускает тесты `/healthz` и `/readyz`, обеспечивая запуск `pytest -k "health or ready"`.

## [2025-10-27] - Amvera deployment profile
### Добавлено
- Конфигурация `amvera.yaml` с выбором ролей `api|worker|tgbot` и единой точкой входа FastAPI/воркера/бота.
- Пример окружения `.env.amvera.example` без секретов и документация по деплою на Amvera.
- Скрипты `app/api.py`, `scripts/worker.py`, `scripts/tg_bot.py` для запуска процессов на платформе.

### Изменено
- `app/config.py` формирует DSN PostgreSQL (rw/ro/rr) и URL Redis через переменные окружения.
- README дополнен разделом «Deploy to Amvera» с проверками готовности и перечнем переменных.

### Исправлено
- Отсутствие централизованного доступа к DSN устраняет дублирование при подключении к БД и Redis.

## [2025-09-26] - Lint workflow consolidation
### Добавлено
- Цель `lint-changed` в `Makefile`, проверяющая только изменённые Python-файлы критичными правилами Ruff.

### Изменено
- `lint-soft` запускает `ruff check . --select E9,F63,F7,F82`, сохраняя alias `lint` для мягкого режима и убирая Black/isort из проверки.
- Цель `check` теперь последовательно вызывает `make lint` и `make test`, гарантируя порядок выполнения.
- В `pyproject.toml` синхронизированы параметры Black/isort (Python 3.10, длина строки 88, стандартное include).

### Исправлено
- Рецепты Makefile выровнены табуляцией, что исключает ошибки выполнения из-за неверных отступов.
- Исправлены ошибки Ruff `F821` в `app/data_providers/sportmonks/provider.py` и `app/lines/aggregator.py`, чтобы мягкий линт отслеживал только критичные нарушения.


## [2025-10-21] - Ruff lint soft/strict workflow
### Добавлено
- Цели `lint-soft` и `lint-strict` в `Makefile`, позволяющие включать строгий режим Ruff по мере готовности.

### Изменено
- `pyproject.toml` включает конфигурацию Ruff (target-version, line-length, исключения, правила и игнорирования).
- Цель `fmt` теперь выполняет `ruff check . --fix` перед `isort` и `black`, чтобы применять авто-правки линтера.
- `lint` по умолчанию перенаправлен на `lint-soft`, чтобы `make check` успешно проходил при существующих предупреждениях.

### Исправлено
- Стабилизирован `make check` за счёт мягкого режима Ruff при сохранении пути к строгому контролю.

# [2025-09-23] - SportMonks ingestion v3
### Добавлено
- Пакет `sportmonks/` (клиент с singleflight, endpoints, cache, repository, schemas) и сервис `services/feature_builder.py`.
- Скрипты `scripts/update_upcoming.py` (cron загрузка фикстур/xG/odds, симуляция и запись в БД/Redis) и `scripts/get_match_prediction.py` (CLI explain по fixture_id).
- Юнит-тесты `tests/sm/test_sportmonks_client_v3.py` покрывают пагинацию, ретраи и парсинг lineups/xGFixture.

### Изменено
- `config.py` расширен TTL профилями (`fixtures_upcoming`, `fixtures_live`, `odds_pre_match`, `odds_inplay`, `reference_slow`).
- `docs/Project.md` описывает новый ingestion pipeline и роль Redis/БД; README дополнен справочными curl-командами SportMonks.
- `services`/`scripts` подключены к новым helper-ам; репозиторий сохраняет прогнозы в таблицу `predictions` с upsert.

### Исправлено
- Деградация xG в lineups fallback к ударам маркируется флагом `degraded_mode`, confidence штрафует отсутствие данных.
- Хранение odds больше не создаёт дубликаты благодаря `ON CONFLICT` и нормализованному ключу `match_key`.

# [2025-10-26] - Offline QA stubs & CI gate
### Добавлено
- Лёгкие стабы `tests/_stubs/{numpy.py,pandas.py,sqlalchemy.py,joblib.py}` и переменная окружения `USE_OFFLINE_STUBS` для их принудительной активации.
- CI job `offline-qa`, запускающий `pytest -q` в окружении без тяжёлых зависимостей и использующий гард `tools/ci_assert_no_binaries.sh` как первый шаг.

### Изменено
- `tests/_stubs/__init__.py` поддерживает одновременное принудительное включение стабов и загрузку одиночных модулей.
- `tests/conftest.py` регистрирует стабы для ML/ORM пакетов и учитывает `USE_OFFLINE_STUBS`.
- Модули `diagtools.{drift,run_diagnostics,golden_regression}` подгружают `numpy`/`pandas` лениво, чтобы CLI импортировались оффлайн.
- Обновлены README и `docs/dev_guide.md` с инструкциями по режиму Offline QA.
- `.github/workflows/ci.yml` расширен новым профилем `offline-qa`.

### Исправлено
- Исключены жёсткие импорты тяжёлых зависимостей в `diagtools.*`, что позволяло CLI падать при отсутствии `numpy/pandas`.

# [2025-10-07] - Value v1.5 best-price & settlement
### Добавлено
- Модули `app/lines/reliability.py`, `app/lines/anomaly.py`, `app/settlement/engine.py`, CLI `diagtools/provider_quality.py`, `diagtools/settlement_check.py`, миграция `20241007_005_value_v1_5.py` и таблица `provider_stats`.
- Best-price роутинг `LinesAggregator.pick_best_route`, сохранение `provider_price_decimal`/`consensus_price_decimal` в `picks_ledger`, новые метрики `provider_reliability_score`, `provider_fresh_share`, `provider_latency_ms`, `odds_anomaly_detected_total`, `picks_settled_total`, `portfolio_roi_rolling`, `clv_mean_pct`.
- Тесты `tests/odds/test_reliability.py`, `tests/odds/test_best_route.py`, `tests/odds/test_anomaly_filter.py`, `tests/value/test_settlement_engine.py`, `tests/bot/test_portfolio_extended.py`, `tests/diag/test_provider_quality.py`, `tests/diag/test_settlement_check.py`.

### Изменено
- `app/value_service.py`, `app/bot/{formatting.py,keyboards.py,routers/commands.py,routers/callbacks.py}` выводят блок «Best price», объяснение выбора провайдера и ROI/CLV в `/portfolio`.
- `diagtools/run_diagnostics.py` расширен секциями Provider Reliability, Best-Price, Settlement & ROI; `config.py`, `.env.example`, README и документация (`docs/{dev_guide.md,user_guide.md,diagnostics.md,Project.md}`) описывают новые параметры и гейты.
- `database/schema.sql` и миграции добавляют `provider_price_decimal`, `consensus_price_decimal`, `roi`, индекс `odds_snapshots_match_time`; `app/value_service.py` и `app/value_clv.py` сохраняют best-price данные в леджер.

### Исправлено
- `diagtools/run_diagnostics` корректно использует настройки порогов при подсчёте надёжности/маршрутов и публикует артефакты `provider_quality.{json,md}` и `settlement_check.{json,md}` в CI.

# [2025-10-05] - Value v1.4 audit
### Добавлено
- Мультипровайдерный агрегатор котировок (`app/lines/aggregator.py`, `app/lines/movement.py`), расчёт CLV и леджер (`app/value_clv.py`, `database/schema.sql`, миграция `20241005_004_value_v1_4`).
- CLI `diagtools/clv_check` с артефактами `value_clv.{json,md}`, CI job `value-agg-clv-gate`, документация (`docs/status/value_v1_4_audit.md`, README, docs/dev_guide.md, docs/user_guide.md, docs/diagnostics.md, docs/Project.md`).
- Тесты: `tests/odds/test_aggregator_basic.py`, `tests/odds/test_movement_closing.py`, `tests/value/test_clv_math.py`, `tests/bot/test_portfolio_and_providers.py`, `tests/diag/test_clv_check.py`, текстовые фикстуры `tests/fixtures/odds_multi/*.csv`.

### Изменено
- Бот `/value`, `/compare`, `/portfolio` выводит consensus-линию, тренды и сводку CLV; `app/value_service.py`, `app/bot/formatting.py`, `app/bot/keyboards.py`, `app/bot/routers/{commands,callbacks}.py` подключены к новому агрегатору и леджеру.
- Диагностика (`diagtools/run_diagnostics.py`, `diagtools/value_check.py`) расширена секциями «Odds Aggregation» и «CLV»; `.github/workflows/ci.yml`, `.env.example`, README и профиль CI отражают новые параметры (`ODDS_PROVIDERS`, `ODDS_PROVIDER_WEIGHTS`, `ODDS_AGG_METHOD`, `ODDS_SNAPSHOT_RETENTION_DAYS`, `CLV_*`, `VALUE_ALERT_UPDATE_DELTA/MAX_UPDATES`).
- Обновлены инструкции (`docs/dev_guide.md`, `docs/user_guide.md`, `docs/diagnostics.md`, `docs/Project.md`, `docs/tasktracker.md`) и статус-аудит (`docs/status/value_v1_4_audit.md`).

### Исправлено
- `diagtools.run_diagnostics` корректно агрегирует CLV даже при пустой БД/отсутствии таблицы `picks_ledger` (защита от `sqlite3.DatabaseError`).
- CI гейты падали без записей `picks_ledger` — теперь `value-agg-clv-gate` предварительно прогревает консенсусные котировки и валидирует средний CLV.

# [2025-09-23] - Value odds integration
### Добавлено
- Пакет `app.lines` (интерфейс `LinesProvider`, CSV/HTTP провайдеры, mapper, SQLite-хранилище odds_snapshots).
- Модули `app/pricing/overround`, `app/value_detector`, `app/value_service` и счетчики Prometheus для value-функций.
- Команды бота `/value`, `/compare`, `/alerts`, а также CLI `diagtools/value_check` и тесты `tests/odds/*`, `tests/bot/test_value_commands.py`, `tests/diag/test_value_check.py`.

### Изменено
- `diagtools/run_diagnostics.py` добавил секцию «Value & Odds», создание провайдера и безопасное закрытие клиентов.
- `app/bot/formatting.py`, `app/bot/routers/commands.py`, `app/bot/storage.py`, `app/metrics.py`, `.env.example`, README и пользовательская/разработческая документация обновлены под value-фичи.

### Исправлено
- Импорт `time` в `diagtools/run_diagnostics.py` больше не конфликтует с `datetime.time`, `tests/odds/test_provider_csv.py` подключает `Path`.

# [2025-02-16] - Stub isolation & canonical ETag keys
### Добавлено
- Пакет `tests._stubs` с загрузчиком `ensure_stubs` для оффлайн-зависимостей и тестов.

### Изменено
- `tests/conftest.py` подключает заглушки только при отсутствии реальных пакетов и обновлённые зависимости.
- `SportmonksETagCache` формирует ключи по HTTP-методу, нормализованному пути и allowlist параметров, сохраняя диагностическую строку.
- Тест `tests/sm/test_etag_cache.py` расширен сценариями канонизации ключа и контроля TTL.

### Исправлено
- TTL ETag-кэша больше не продлевается при ответах 304, исключая зависание устаревших выборок.

# [2025-02-15] - Offline dependency stubs
### Добавлено
- Текстовые заглушки `pydantic`, `pydantic_settings`, `httpx`, `prometheus_client`, `aiogram`, `redis`, `rq` для запуска оффлайн-тестов.
- Asyncio-раннер в `tests/conftest.py` и вспомогательные билдеры клавиатур для aiogram.

### Изменено
- `SportmonksProvider` игнорирует фикстуры без идентификаторов лиги и хранит ETag по endpoint без параметров.
- Тесты свежести коммитят тестовые данные SQLite для корректной оценки порогов.

### Исправлено
- `diagtools.freshness` и bot-сервисы теперь импортируются без внешних зависимостей; pytest-сценарии используют локальный event loop.

# [2025-02-14] - SportMonks offline QA
### Добавлено
- Текстовые фикстуры `tests/fixtures/sm/*.json`, оффлайн-режим `scripts/sm_sync.py --dry-run` и CSV отчёт о коллизиях команд в `reports/diagnostics/`.
- Комплект тестов SportMonks: `tests/sm/test_windows.py`, `tests/sm/test_retry_rps.py`, `tests/sm/test_etag_cache.py`, `tests/sm/test_allowlist.py`, `tests/sm/test_mapping_collisions.py`, `tests/sm/test_upsert_idempotent.py`, а также `tests/model/test_features_ingestion.py`, обновлённый `tests/bot/test_staleness_badges.py` и `tests/ops/test_freshness_gate.py`.
- CLI `python -m diagtools.freshness` и сводка свежести по лигам в Markdown/JSON отчётах диагностики.

### Изменено
- `SportmonksProvider` и `scripts/sm_sync.py` используют ETag/Last-Modified, строгую фильтрацию по allowlist и dry-run без сети.
- README и `docs/diagnostics.md` описывают оффлайн-тесты, включение ETag и метрики `sm_*`; бот отображает бейджи `🟢/⚠️`.

### Исправлено
- Метрики `sm_requests_total`/`sm_ratelimit_sleep_seconds_total` покрывают ретраи и лимиты; `sm_freshness_hours_max` обновляется при диагностике.
- Диагностика свежести отдаёт статусы OK/WARN/FAIL и корректные exit-коды для CI.

# [2025-10-14] - SportMonks ingest v1
### Добавлено
- Асинхронный клиент `app/data_providers/sportmonks` с ретраями, токен-бакетом и DTO.
- SQLite-репозиторий, CLI `scripts/sm_sync.py`, метрики Prometheus и таблицы `sm_*`, `map_*`.
- Диагностика свежести данных и комплект юнит-тестов (`tests/sm/*`, `tests/bot/test_staleness_badges.py`).

### Изменено
- Бот отображает бейджи свежести, контекст матчей и использует `SportmonksDataSource`.
- Планировщик переобучения пропускает запуск при устаревших данных; README описывает ETL и новые ENV.

### Исправлено
- —

# [2025-10-12] - Diagnostics v2.1 packaging & drift gate
### Добавлено
- Пакет `diagtools` с CLI-энтрипойнтами `diag-run` и `diag-drift`, избавляющими от `sys.path` хака и упрощающими запуск из CI.
- Стратифицированные отчёты по дрифту (global/league/season) с CSV/Markdown/JSON, reference parquet + checksum и PNG-гистограммами.
- Prometheus-метрики `drift_last_run_ts`, `drift_psi_max`, `drift_failures_total`, а также GitHub Actions job `diagnostics-drift` с публикацией артефактов.

### Изменено
- `diagtools.run_diagnostics` интегрирует новый API дрифта и прокидывает статусы в общую сводку.
- Документация (`docs/diagnostics.md`, README) обновлена под новые команды, параметры `DRIFT_ROLLING_DAYS`, `DRIFT_KS_P_*` и сценарии обновления reference.

### Исправлено
- Стандартные профили Makefile и workflow используют `python -m diagtools.*`, исключая обращения к устаревшему `tools/`.

# [2025-10-08] - Drift diagnostics import fix
### Добавлено
- —

### Изменено
- —

### Исправлено
- В `tools/drift_report.py` добавлено подключение корня проекта в `sys.path`, благодаря чему скрипт корректно импортирует `tools.golden_regression` при запуске из CLI.

# [2025-10-07] - Diagnostics automation & bot fixes
### Добавлено
- Скрипт `tools/run_diagnostics.py` для сквозной диагностики ENV/моделей/бота/ops с генерацией `reports/diagnostics/*`.
- Артефакты диагностики: Markdown/JSON отчёты, CSV модулей A/B, логи pytest/smoke.

### Изменено
- Регрессия `/run_simulation` покрывается e2e-диагностикой; резюме статусов выводится в консоль.

### Исправлено
- Исправлена индентация в `telegram/bot.py::_set_bot_commands`, устраняющая `IndentationError` при импорте.
- В `telegram/utils/token_bucket.py` восстановлена заголовочная @file-докстрока во избежание синтаксической ошибки.

# [2025-09-23] - Product v1 bot commands
### Добавлено
- Пакет `app/bot` с кешированием, форматированием, inline-клавиатурами и SQLite-хранилищем предпочтений.
- Новые aiogram-роутеры (`commands.py`, `callbacks.py`) с поддержкой `/today`, `/match`, `/explain`, `/league`, `/subscribe`, `/export`, `/about`, `/admin`.
- Генерация CSV и PNG отчётов (`PredictionFacade.generate_csv/png`), таблицы `user_prefs`, `subscriptions`, `reports` в `database/schema.sql`.
- Документация `docs/user_guide.md`, `docs/dev_guide.md`, тесты `tests/bot/*`, метрики `bot_digest_sent_total`, `render_latency_seconds`.

### Изменено
- README, `.env.example`, `docs/Project.md` обновлены под архитектуру Product v1 и ENV (`PAGINATION_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `ADMIN_IDS`, `DIGEST_DEFAULT_TIME`).
- `telegram/handlers/__init__.py` подключает новый root-router `build_bot_router()`.
- `config.Settings` валидирует новые параметры, `requirements.txt` включает `matplotlib>=3.8`.

### Исправлено
- Устранены дубли команд: старые роутеры исключены из регистрации, кеш очистки вынесен в `/admin reload`.
- Тестовый контракт `.env` расширен, чтобы избежать пропуска новых ключей окружения.

# [2025-10-05] - Hardening Pack v1
### Добавлено
- Модуль `app/runtime_lock.py`, health-сервер и универсальный `retry_async` с тестами `tests/test_runtime_lock.py`, `tests/test_env_contract.py`, `tests/test_data_paths.py`.
- Проверка записи путей и dry-run лог в `main.py`; опция `/health` и обновлённый smoke job.

### Изменено
- Логирование переведено на стандартный `logging` с `RotatingFileHandler` и logfmt/JSON форматами.
- `main.py`, `telegram/bot.py`, `.env.example`, `amvera.yaml`, `README.md`, `docs/deploy-amvera.md` синхронизированы с ENV-контрактом и graceful shutdown.

### Исправлено
- Повторный запуск сообщает о занятом lock без stack trace; корректно освобождаются ресурсы Redis/health-сервер.
- Сигналы `SIGTERM/SIGINT` останавливают polling c соблюдением таймаута `SHUTDOWN_TIMEOUT`.

## [2025-09-30] - Amvera Ops v2 readiness & maintenance
### Добавлено
- Эндпоинт `/ready` и `RuntimeState` для отражения готовности компонентов.
- Prometheus-метрики бота, счётчики команд и периодическое обновление размера SQLite.
- Ежедневные бэкапы SQLite с ротацией, недельный `VACUUM/ANALYZE` и тесты (`tests/test_db_maintenance.py`, `tests/test_readiness.py`, `tests/test_metrics_server.py`).
- Токен-бакет для rate-limit и middleware идемпотентности команд.

### Изменено
- Основной цикл (`main.py`) стартует сервер метрик по `ENABLE_METRICS`, учитывает фиче-флаги polling/scheduler и обновляет readiness.
- Логи маскируют секреты по ключам `*_TOKEN`, `*_KEY`, `PASSWORD` на уровне адаптера.
- Документация (`README.md`, `docs/deploy-amvera.md`, `.env.example`) описывает `/health` vs `/ready`, фиче-флаги и регламент бэкапов.

### Исправлено
- `RuntimeLock` очищает устаревшие lock-файлы с мёртвым PID.
- `storage/persistence.py` применяет безопасные PRAGMA на всех SQLite-соединениях.

## [2025-10-03] - Amvera deployment support
### Добавлено
- Конфигурация `amvera.yaml` для окружения Python/pip 3.11 с точкой входа `main.py` и монтированием `/data`.
- Документ [docs/deploy-amvera.md](deploy-amvera.md) с инструкциями по перемещению SQLite, smoke-проверкам и сценариям доставки.
- Джоб GitHub Actions `amvera-smoke`, запускающий `python -m main --dry-run` с временными путями `/data`.

### Изменено
- Путь всех изменяемых данных (SQLite, отчёты, артефакты, логи) переведён на конфигурируемые переменные (`DB_PATH`, `REPORTS_DIR`, `MODEL_REGISTRY_PATH`, `LOG_DIR`) с дефолтом `/data/...`.
- `main.py` и `telegram/bot.py` поддерживают флаг `--dry-run` и задержку `BOT_STARTUP_DELAY` перед long polling.
- README и `.env.example` актуализированы под требования Amvera (PYTHONUNBUFFERED, новые ENV, использование `/data`).

### Исправлено
- Исключены записи в репозиторий при генерации отчётов/логов: все пути создаются в `/data`, что устраняет ошибки `sqlite is readonly`.

## [2025-10-02] - E6.18: Prediction worker dirty payload coverage
### Добавлено
- Параметризованные тесты `tests/workers/test_prediction_worker_errors.py` проверяют ошибки ядра,
  таймаут Redis-lock и обработку «грязного» payload (NaN/negative).

### Изменено
- Тестовый двойник `SpyPredictor` принимает валидатор для эмуляции проверок входных данных и маскировки секретов в логах.

### Исправлено
- Исключены регрессии при обработке NaN/отрицательных `n_sims` — воркер возвращает предсказуемую ошибку без дублирования job.

## [2025-10-01] - E6.17: Redis factory retry coverage
### Добавлено
- Юнит-тесты `tests/database/test_redis_factory_backoff.py` моделируют backoff с jitter и успешное переподключение RedisFactory.
- `workers/redis_factory.RedisFactory` поддерживает экспоненциальный backoff, jitter и маскирование DSN при повторных попытках.

### Изменено
- Логика переподключения RedisFactory использует биндинг logger для маскировки DSN и повторные попытки с контролируемыми задержками.

### Исправлено
- Исключение при исчерпании повторных попыток RedisFactory содержит понятное сообщение без утечки секретов.

## [2025-09-30] - E6.16: Prediction worker log hardening
### Добавлено
- Расширены регресс-тесты `tests/workers/test_prediction_worker_errors.py` для проверки маскировки логов,
  таймаутов Redis-lock и обработки «грязного» payload.

### Изменено
- Тестовый двойник очереди журналирует события воркера для контроля сообщений без секретов.

### Исправлено
- Исключены потенциальные утечки токенов в сообщениях логов при падении ядра предсказаний.

## [2025-09-29] - E6.15: Queue adapter edge coverage
### Добавлено
- Тесты `tests/workers/test_queue_adapter_edges.py`, покрывающие редкие статусы RQ и маскирование ошибок очереди.

### Изменено
- —

### Исправлено
- —

## [2025-09-28] - E6.14: Makefile coverage pipeline cleanup
### Добавлено
- —

### Изменено
- Цели `test-all` и `coverage-html` выполняют pytest с контролем покрытия и генерацией HTML-отчёта без предварительного удаления артефактов, сохраняя единый пайплайн enforcement.

### Исправлено
- —

## [2025-09-27] - E6.13: Coverage gaps script trim
### Добавлено
- —

### Изменено
- Скрипт `tools/coverage_gaps.py` оставляет анализ только через элементы `<line>` и укладывается в требуемый лимит в 200 строк.

### Исправлено
- Исправлен досрочный выход из обхода классов и избыточные пустые строки перед блоком запуска.

## [2025-09-26] - E6.12: Coverage gaps top-20 refresh
### Добавлено
- —

### Изменено
- Скрипт `tools/coverage_gaps.py` формирует единый ТОП-20 файлов по пропущенным строкам в критических пакетах и пересобирает Markdown-отчёт `reports/coverage_gaps.md`.

### Исправлено
- Уточнено построение диапазонов пропущенных строк и сообщение об отсутствии данных в отчёте.

## [2025-09-25] - E6.11: Coverage enforcement parser tweaks
### Добавлено
- —

### Изменено
- Парсер Cobertura учитывает только прямые элементы `<line>` внутри `<lines>` для точного подсчёта пропущенных строк.
- Сообщение о провале порогов покрытия сокращено до лаконичного формата «coverage check failed».

### Исправлено
- Исключено двойное суммирование строк покрытия при вложенных тегах.

## [2025-09-24] - E6.10: Актуализация exclude_lines coverage
### Добавлено
- —

### Изменено
- Правило `exclude_lines` в `.coveragerc` приведено к шаблону `if __name__ == .__main__.:` для единообразной фильтрации блоков запуска.

### Исправлено
- —

## [2025-09-24] - E6.8: Coverage omit refresh
### Добавлено
- —

### Изменено
- Список `omit` в `.coveragerc` очищен от устаревшего `scripts/entrypoint.sh`, оставлен шаблон `scripts/*.sh`.

### Исправлено
- —

## [2025-09-24] - E6.7: DB router fallback coverage
### Добавлено
- Тесты `tests/database/test_db_router_fallbacks.py`, проверяющие fallback чтения и негативные сценарии запуска.

### Изменено
- —

### Исправлено
- Контролируемые ошибки при неверных DSN и таймаутах движка подтверждены регресс-тестами.

## [2025-09-24] - E6.6: Prediction worker error guards
### Добавлено
- Тесты `tests/workers/test_prediction_worker_errors.py`, проверяющие обработку ошибок ядра, таймаутов Redis-lock и валидацию payload.

### Изменено
- —

### Исправлено
- Исключены потенциальные утечки секретов в сообщениях об ошибках при провале генерации предсказаний.

## [2025-09-24] - E6.5: Makefile coverage цели
### Добавлено
- Цель `reports-gaps`, вызывающая `python -m tools.coverage_gaps` для актуализации Markdown-отчёта пропусков.

### Изменено
- Цели `test-all` и `coverage-html` запускают pytest с отчётом покрытия и жёсткими порогами `tools.coverage_enforce` (total ≥80%, пакеты ≥90%, топ-20 файлов).

### Исправлено
- —

## [2025-09-24] - E6.4: Отчёт по coverage gaps
### Добавлено
- Скрипт `tools/coverage_gaps.py`, анализирующий `coverage.xml` и формирующий Markdown-отчёт `reports/coverage_gaps.md` с ТОП-20 дыр по пакетам workers, database, services и core/services.

### Изменено
- Структура `reports/coverage_gaps.md` приведена к новому формату автоматической генерации с разбивкой по пакетам.

### Исправлено
- —

## [2025-09-24] - E6.3: Актуализация конфигурации coverage
### Добавлено
- Опция `relative_files = True` в `.coveragerc` для корректного отображения путей в отчётах.

### Изменено
- Явно перечислены каталоги `telegram`, `workers`, `services`, `core`, `database`, `scripts` в разделе `source`.
- Добавлены правила `exclude_lines` и уточнён список исключений отчёта покрытия.

### Исправлено
- Исключены ложные срабатывания по строкам `if __name__ == '__main__':` и блокам `TYPE_CHECKING` при расчёте покрытия.

## [2025-09-23] - E6.2: Жёсткая конфигурация coverage
### Добавлено
- `.coveragerc` с настройками statement coverage и исключениями для миграций, документации, тестов и shell-скриптов.
- Модуль `tools.coverage_enforce`, читающий `coverage.xml`, проверяющий пороги и обновляющий `reports/coverage_summary.json`.

### Изменено
- Цели `Makefile` (`test-all`, `coverage-html`) теперь генерируют `coverage.xml`, вызывают новый enforcement и строят HTML через `coverage html`.
- Workflow CI добавляет шаг `coverage-enforce`, README описывает конфигурацию `.coveragerc` и пороги пакетов.

### Исправлено
- Сборка падает с кодом 2 при покрытии <80% либо <90% по `workers/`, `database/`, `services/`, `core/services/` на основании `coverage.xml`.

## [2025-09-23] - E6: Покрытие отрицательных сценариев
### Добавлено
- Юнит-тесты ошибок Telegram-команд (`tests/bot/test_handlers_errors.py`) и виджетов (`tests/telegram/test_widgets_escape.py`).
- Тесты инфраструктуры: `tests/workers/test_queue_adapter_errors.py`, `tests/workers/test_task_manager_policies.py`, `tests/database/test_db_router_errors.py`, `tests/services/test_predictor_determinism.py`, `tests/scripts/test_prestart.py`, `tests/security/test_masking.py`.
- Раздел «After» в `reports/coverage_gaps.md` с закрытыми провалами и дельтой.

### Изменено
- `workers/queue_adapter.py` расширен маппингами статусов RQ и безопасным построением сообщений об ошибке.

### Исправлено
- Маскирование DSN/URL в логах `scripts/prestart` и `workers.redis_factory` подтверждено тестами безопасности.
- `workers/task_manager` проверен на прокидывание TTL/priority и корректную обработку исключений очереди.

## [2025-09-22] - E6: Покрытие и отчёты CI
### Добавлено
- Скрипты `reports/bot_e2e_snapshot.py` и `reports/rc_summary.py`, сохраняющие snapshot ответов бота и RC-итог с версиями/coverage.
- Утилиты `scripts/coverage_utils.py` и `scripts/enforce_coverage.py` для подсчёта покрытия и экспорт `reports/coverage_summary.json`.
- Makefile-профили `test-fast`, `test-smoke`, `test-all`, `coverage-html` с единым запуском pytest.

### Изменено
- GitHub Actions теперь выполняет последовательность `lint → test-fast → smoke → coverage → reports → artifacts` и публикует артефакт `coverage-and-reports`.
- README задокументировал новые таргеты, пороги покрытия (≥80% суммарно, ≥90% для workers/database/services/core/services) и артефакты CI.

### Исправлено
- Контроль покрытия падает при регрессе total/critical пакетов; отчёты маскируют секреты (используется `mask_dsn`).

## [2025-09-21] - E5: Подготовка Docker-окружения для Amvera
### Добавлено
- Многоступенчатый `Dockerfile`, `.dockerignore` и `scripts/entrypoint.sh` с проверкой обязательных переменных окружения.
- `scripts/prestart.py`, выполняющий `alembic upgrade head` и health-check PostgreSQL/Redis с маскировкой DSN.

### Изменено
- `Makefile` получил цели `docker-build`/`docker-run`, использующие теги из `APP_VERSION` и `GIT_SHA`.
- `README.md` дополнен разделом про деплой на Amvera и описанием prestart-процедуры.

### Исправлено
- Экспортирован `mask_dsn()` из `database.db_router` и добавлен `RedisFactory.health_check()` для корректной диагностики старта.

## [2025-09-20] - E4: Recommendation engine invariants
### Добавлено
- Унифицированный `RecommendationEngine.generate_prediction` с нормализацией 1X2/Totals/BTTS и top-k счётов.
- Сервис `core/services/predictor.py` и DI-воркер с поддержкой статусов и Redis-lock.
- Тесты `tests/ml/test_prediction_invariants.py` и `tests/workers/test_prediction_worker.py` для проверки инвариантов и очереди.
### Изменено
- README получил раздел «ML-ядро и инварианты», Project.md описывает новый фасад и детерминированный seed.
### Исправлено
- Исключены `await` синхронных методов и глобальные клиенты в worker; ошибки audit.md по несуществующим API устранены.

## [2025-09-19] - E3: Telegram UX overhaul
### Добавлено
- Ди-инжектируемые обработчики `/help`, `/model`, `/today`, `/match`, `/predict` с новым модулем форматирования `telegram/widgets.py`.
- Тесты `tests/bot/test_handlers_smoke.py` и `tests/bot/test_formatting.py` для smoke-проверок и форматирования.
- README раздел «Команды бота и примеры» с описанием сценариев.
### Изменено
- Регистрация роутеров Telegram переведена на `telegram.handlers.register_handlers` с общим контейнером зависимостей.
- Команда `/predict` ставит задачи через адаптер `TaskManagerQueue` и проверяет ввод с учётом разных тире.
### Исправлено
- Сообщения об ошибках `/match` и `/predict` приводятся к лаконичным формулировкам («Матч не найден», «Неверный id», «Нужно указать обе команды»).

## [2025-09-17] - Асинхронный роутер БД и Alembic
### Добавлено
- Модуль `database/db_router.py` с управлением асинхронными сессиями чтения и записи.
- Асинхронное окружение Alembic (`database/migrations`) с первой ревизией `predictions`.
- Тесты `tests/database/test_db_router.py` для проверки роутера и детекции DSN.
### Изменено
- Конфигурация `Settings` дополнена параметрами пулов и таймаутов базы данных.
### Исправлено
- —

## [2025-09-18] - Audit and refactor planning for Amvera
### Добавлено
- Добавлен отчёт `audit.md` с перечнем рисков перехода на Amvera.
- Подготовлен план `refactor_plan.md` с этапами E1–E7.
### Изменено
- —
### Исправлено
- —

## [2025-09-17] - Redis cache hardening
### Добавлено
- Тесты `tests/database/test_cache_postgres.py` для проверки TTL, versioned key и лайнап-кэша.
### Изменено
- `database/cache_postgres.py` получил docstring с метаданными и синхронный `versioned_key`.
### Исправлено
- Убрано ошибочное `await get_settings()` в Redis-хелперах и восстановлено кэширование лайнапов через `set_with_ttl`.

## [2025-09-17] - CI coverage artifacts and lint refinements
### Добавлено
- Запуск `pytest --cov=app/data_processor` в numeric job и публикация HTML-отчёта покрытия.
- Раздел README «Coverage artifacts в CI» с путями к `htmlcov/` и SQLite.
### Изменено
- Линтерный job в CI использует `python -m ruff check . --exit-non-zero-on-fix`, `python -m black --check .`, `python -m isort --check-only .`.
- docs/tasktracker.md отмечает завершение плана Integrator Part 1–3.
### Исправлено
- —

## [2025-09-16] - CLI retrain orchestration
### Добавлено
- CLI `scripts/cli.py` с подкомандами `retrain run/schedule/status` и записью отчётов.
- Smoke-тест `tests/smoke/test_cli_retrain.py` для переобучения и планировщика.
### Изменено
- README.md, ARCHITECTURE.md, reports/RUN_SUMMARY.md описывают новый CLI и артефакты.
- docs/tasktracker.md зафиксировал прогресс задачи.
### Исправлено
- —

## [2025-09-16] - extracted data_processor with tests (≥80%)
### Добавлено
- Полноценное формирование признаков матчей с историческими агрегатами и расчётом rest_days.
- Табличное преобразование в матрицы признаков с автоматической подготовкой обучающих выборок.
- Набор модульных тестов для build_features, validate_input и to_model_matrix.
### Изменено
- Валидация входных данных автоматически проверяет ключевые колонки матчей и типы.
- to_model_matrix возвращает tuple для матчей и логирует целевую переменную через log1p.
### Исправлено
- Исключена утечка таргета из rolling агрегатов и стабилизированы прогнозы GLM.

## [2025-09-16] - Data processor scaffolding
### Добавлено
- Заглушечный пакет `app/data_processor` с модулями `validate`, `features`, `matrix` и версией пакета.
- Тесты `tests/data_processor` на проверку ошибок при пустом `DataFrame`.
### Изменено
- Обновлён интерфейс `app.data_processor` для экспорта новых заглушек.
### Исправлено
- —

## [2025-09-15] - Release candidate v1.0.0-rc1
### Добавлено
- APP_VERSION field and version labels in metrics and reports.
- requirements.lock and Makefile targets deps-lock/deps-sync.
- CI exports APP_VERSION and GIT_SHA with RC summary step.
### Изменено
- README and ARCHITECTURE mention version visibility and offline lock.
### Исправлено
- .env.example synced with Settings.

## [2025-09-15] - Simulation pipeline integration
### Добавлено
- Monte-Carlo simulation integrated into prediction pipeline with SQLite writes and Markdown reports.
- CI uploads simulation artifacts and integration test ensures markets are persisted.
### Изменено
- README.md, ARCHITECTURE.md, reports/RUN_SUMMARY.md.
### Исправлено
- —

## [2025-09-15] - Entropy analytics and simulation settings
### Добавлено
- Модуль `ml/metrics/entropy.py` и тесты.
- Параметры окружения `SIM_RHO`, `SIM_N`, `SIM_CHUNK`.
- Энтропии рынков в `services/simulator.py`.
### Изменено
- `.env.example`, `config.py`, `app/config.py`, `ml/sim/bivariate_poisson.py`.
### Исправлено
- —

## [2025-09-15] - Simulation markets and calibration
### Добавлено
- Bi-Poisson simulator with correlated goals and market aggregations (1x2, totals, BTTS, CS).
- Calibration helpers (`ml/calibration.py`) and CLI flags `--calibrate`, `--report-md`, `--write-db`.
- SQLite storage layer `storage/persistence.py` for predictions.
### Изменено
- README, ARCHITECTURE.md, docs/tasktracker.md, reports/RUN_SUMMARY.md.
### Исправлено
- —

## [2025-09-15] - Modifiers validation
### Добавлено
- Метрики модификатора base vs final в `PredictionPipeline`.
- CLI `scripts/validate_modifiers.py` и smoke-тест.
- CI-гейт проверки модификаторов.
### Изменено
- README, ARCHITECTURE.md, docs/Project.md, workflow CI.
### Исправлено
- —

## [2025-09-15] - Monte-Carlo simulator
### Добавлено
- Модуль `ml/sim/bivariate_poisson.py`, сервис `services/simulator.py`, скрипт `run_simulation.py` и тесты симуляций.
### Изменено
- —
### Исправлено
- —

## [2025-09-15] - Dynamic modifiers
### Добавлено
- Модель `ml/modifiers_model.py`, скрипт `train_modifiers.py` и тесты `test_modifiers.py`.
- Интеграция модификаторов в `PredictionPipeline` с логом `modifiers_applied`.
### Изменено
- —
### Исправлено
- —

## [2025-09-15] - GLM training pipeline
### Добавлено
- Скрипт `scripts/train_glm.py` и тест `tests/ml/test_glm_training.py`.
- Поддержка `glm_home` и `glm_away` в `PredictionPipeline`.
### Изменено
- Project.md описывает загрузку GLM из LocalModelRegistry.
### Исправлено
- —

## [2025-09-15] - Dependency cleanup and lint pins
### Добавлено
- Пины версий isort, black, flake8, ruff, mypy и pre-commit.
### Изменено
- requirements.txt и constraints.txt синхронизированы.
### Исправлено
- —

## [2025-09-15] - Ruff warnings cleanup
### Добавлено
- —
### Изменено
- Аннотации типов в prediction_pipeline и retrain_scheduler используют современный синтаксис.
### Исправлено
- Предупреждения Ruff F401, I001, UP037, UP035, UP045.

## [2025-09-15] - Ruff leftovers cleanup and smoke
### Добавлено
- —
### Изменено
- Цель `smoke` печатает статусы и падает при ошибке.
### Исправлено
- Предупреждения Ruff B904, C401, ERA001.

## [2025-09-15] - SportMonks stub and Ruff cleanup
### Добавлено
- Автоматическое включение STUB SportMonks при отсутствии ключа API.
### Изменено
- —
### Исправлено
- Предупреждения Ruff B904, B025, ERA001, UP038, C401; исправлен `invalid-syntax` в `telegram/models.py`.

## [2025-09-15] - Offline pre-commit ruff fix
### Добавлено
- Локальные хуки `trailing-whitespace` и `end-of-file-fixer` для офлайн линтинга.
### Изменено
- Хук Ruff запускается как `ruff check --fix`.
- `isort` и `black` вызываются через `python -m`.
- Цель `pre-commit-offline` в `Makefile` использует `--config` и `--all-files`.
### Исправлено
- —

## [2025-09-15] - Sentry flag and metrics labels
### Добавлено
- Переменные `SENTRY_ENABLED`, `GIT_SHA` и метки `service/env/version` в метриках.
- Счётчик `jobs_registered_total` в `runtime_scheduler` и `/__smoke__/retrain`.
### Изменено
- Инициализация Sentry и `/metrics` через фичефлаг.
### Исправлено
- Предупреждения Ruff `B034` и `E402`.

## [2025-09-15] - CI staged workflow
### Добавлено
- Отдельные стадии `lint`, `unit`, `e2e/smoke` и `numeric` в CI.
### Изменено
- Стадия `numeric` использует локальные колёса через `pip.conf` и падает при пропуске `@needs_np`.
### Исправлено
- —

## [2025-09-15] - Offline numeric stack support
### Добавлено
- Каталог `wheels/` и настройка `pip` для офлайн-установок.
- Хук `ruff` в `.pre-commit-config.offline.yaml`.
- Раздел README "CI numeric enforcement".
### Изменено
- `pip.conf` использует локальный кэш колёс.
- `.pre-commit-config.offline.yaml` расширен `ruff`-хуком.
### Исправлено
- —

## [2025-09-15] - Enforce numeric test suite
### Добавлено
- Жёсткая проверка `needs_np` тестов в CI.
### Изменено
- Удалена переменная окружения `NEEDS_NP_PATTERNS`, упрощён `conftest_np_guard`.
- Переименован smoke-тест `TaskManager.cleanup` во избежание конфликтов.
### Исправлено
- Bivariate Poisson utilities совместимы с NumPy 2.x.

## [2025-09-15] - Numpy guard and CI fallback
### Добавлено
- Защита тестов, требующих numpy/pandas, с шаблонами через ENV.
### Изменено
- CI запускает ruff/isort/black при падении pre-commit.
- README и pytest.ini документируют пропуск тестов без численного стека.
### Исправлено
- —

## [2025-09-15] - Pin numpy/pandas versions
### Добавлено
- Ограничения numpy>=1.26,<2.0 и pandas==2.2.2.
### Изменено
- README и ARCHITECTURE: описан ML-стек.
### Исправлено
- —

## [2025-09-18] - Cleanup TODOs and CI smoke
### Добавлено
- Шаги smoke и e2e в CI.
### Изменено
- README и ARCHITECTURE: указаны LocalModelRegistry, stub SportMonks и ключевые ENV.
- scripts/train_model.py использует `SEASON_ID` из окружения.
### Исправлено
- Удалены устаревшие TODO в обработчиках и train_model.

## [2025-09-17] - Env contract and pipeline tests
### Добавлено
- Контрактный тест `.env.example` ↔ `app.config.Settings`.
- E2E тест PredictionPipeline с LocalModelRegistry.
- Smoke-тест TaskManager.cleanup.
### Изменено
- Исправлен `.pre-commit-config.offline.yaml`.
- `.env.example` синхронизирован с настройками Sentry.
- README.md и ARCHITECTURE.md дополнены разделом о тестах.
### Исправлено
- —

## [2025-09-16] - ENV contract and cleanup utilities
### Добавлено
- LocalModelRegistry для сохранения моделей по сезонам.
- Функции TaskManager.clear_all и cleanup с тестами.
### Изменено
- .env.example и app/config.py синхронизированы с переменными ENV, PROMETHEUS__*, RETRAIN_CRON.
- Заголовки в telegram/middlewares и ml/* переписаны на docstrings.
### Исправлено
- —

## [2025-09-15] - SportMonks stub client and tests
### Добавлено
- Клиент SportMonks с режимом заглушки.
- Тесты для проверки stub-логики.
### Изменено
- .env.example документирует переменную SPORTMONKS_STUB.
### Исправлено
- —

## [2025-09-15] - Add smoke tests and CI offline lint
### Добавлено
- Smoke-тесты для базовых эндпоинтов.
### Изменено
- CI использует `make pre-commit-smart` для офлайн линтинга.
### Исправлено
- —

## [2025-09-15] - Unify observability and add metrics test
### Добавлено
- Smoke-тест для эндпоинта /metrics.
### Изменено
- Метрики отдаются через PlainTextResponse с указанием версии.
### Исправлено
- Удалён дублирующий модуль observability.

## [2025-09-15] - Convert data_processor headers to docstrings
### Добавлено
- —
### Изменено
- Заголовки файлов data_processor переписаны на докстринги.
### Исправлено
- —

## [2025-09-15] - Align env example with config
### Добавлено
- Добавлены переменные окружения TELEGRAM_BOT_TOKEN, SPORTMONKS_API_KEY, ODDS_API_KEY, DATABASE_URL, REDIS_HOST, REDIS_PORT, REDIS_DB в .env.example.
### Изменено
- PrometheusSettings и RateLimitSettings используют алиасы для переменных окружения.
### Исправлено
- —

## [2025-09-14] - Repository inventory refresh
### Добавлено
- Обновлён отчёт `reports/INVENTORY.md` с актуальными снимками документации, структуры и TODO.
### Изменено
- —
### Исправлено
- —

## [2025-09-13] - Repository inventory report
### Добавлено
- Отчёт `reports/INVENTORY.md` с инвентаризацией репозитория.
### Изменено
- —
### Исправлено
- —

## [2025-09-12] - Smart pre-commit fallback
### Добавлено
- Скрипт `scripts/run_precommit.py` и конфиг `.pre-commit-config.offline.yaml` для офлайн запуска.
- Цель `pre-commit-smart` в Makefile.
- Переменная `PRE_COMMIT_HOME` для кеша хуков.
### Изменено
- README.md: инструкция по офлайн запуску pre-commit.
### Исправлено
- —

## [2025-09-12] - Feature-flag retrain scheduler and smoke endpoint
### Добавлено
- In-memory runtime scheduler adapter `workers/runtime_scheduler.py`.
- Smoke endpoint `/__smoke__/retrain` with feature flag `RETRAIN_CRON`.
### Изменено
- `app/main.py`: интеграция планировщика переобучения.
- `.env.example`, `README.md`: документация по флагу `RETRAIN_CRON`.
### Исправлено
- —

## [2025-09-12] - Скелеты сервисов и планировщика
### Добавлено
- Минимальные скелеты `services/prediction_pipeline.py` и `workers/retrain_scheduler.py`.
- Тесты `test_services_workers_minimal.py`.
### Изменено
- README.md: добавлен раздел Services & Workers.
- .env.example: добавлен блок Services/Workers.
### Исправлено
- —
## [2025-09-12] - Синхронизация pandas и метрики
### Добавлено
- Реализована функция `record_prediction` с обновлением скользящих метрик.
### Изменено
- В `requirements.txt` закреплена версия `pandas==2.2.2`.
### Исправлено
- Отправка предупреждений Sentry при высоком ECE.

## [2025-09-12] - Проектный аудит и план доводки
### Добавлено
- Файлы `reports/PROJECT_AUDIT.md` и `reports/ACTION_PLAN.md`.
### Изменено
- Обновлён `docs/tasktracker.md` новой задачей.
### Исправлено
- —

## [2025-09-12] - Детектор синтаксических ошибок и выборочный lint
### Добавлено
- Скрипт `scripts/syntax_partition.py` для разделения parseable и обновления исключений.
### Изменено
- Цель `lint-app` в Makefile работает только по parseable файлам.
### Исправлено
- Актуализированы `.env.blackexclude` и `.ruffignore`.

## [2025-09-12] - Точечный Ruff игнор и lint-app
### Добавлено
- Цель `lint-app` для строгой проверки `app`.
### Изменено
- Секция `per-file-ignores` в `ruff.toml` для `__init__.py` и `tests`.
### Исправлено
- Автоформатирование и сортировка импортов в `app`.

## [2025-09-12] - Глобальная проверка численного стека
### Добавлено
- Проверка стека NumPy/Pandas и автоматический пропуск тестов.
### Изменено
- Тесты, зависящие от numpy/pandas, помечены `needs_np` или адаптированы под пропуск.
### Исправлено
- Тест настроек обновлён для корректной работы с переменными окружения.

## [2025-09-12] - Ленивая проверка lint и защита тестов
### Добавлено
- Локальный конфиг `pip.conf` с поддержкой зеркал.
### Изменено
- Цель `lint` параметризована флагом `LINT_STRICT`.
- Тесты используют `pytest.importorskip` для numpy и pandas.
### Исправлено
- —

## [2025-09-12] - Пины численного стека и Ruff игнор
### Добавлено
- Файл `constraints.txt` с закреплёнными версиями numpy/pandas/scipy/pyarrow.
- Файл `.ruffignore` и скрипт `scripts/ruff_partition.py`.
### Изменено
- Цель `setup` в `Makefile` использует `constraints.txt` и добавлена цель `deps-fix`.
### Исправлено
- —

## [2025-09-12] - Стабилизация Black и Ruff
### Добавлено
- Автофикстура `_defaults_env` в тестах.
- Блок шумных артефактов в `.gitignore`.

### Изменено
- Makefile использует `BLACK_EXCLUDE` и ограничивает Ruff каталогами `app` и `tests`.
- Переписан `scripts/black_partition.py` с поддержкой `--force-exclude`.

### Исправлено
- Обновлены `.gitignore` и `.env.blackexclude` для проблемных файлов Black.

## [2025-09-11] - Обновление Black, Ruff и настроек
### Добавлено
- Алиасы `APP_NAME` и `DEBUG` для модели `Settings`.
- Автогенерация `extend-exclude` в `scripts/black_partition.py`.
### Изменено
- Переписана конфигурация Black и Ruff.
- Тестовая фикстура включает метрики и сбрасывает кэш настроек.
### Исправлено
- В `requirements.txt` указана зависимость `numpy>=1.26`.

## [2025-09-11] - Стабилизация setup и автоформатирования
### Добавлено
- Конфиг Black в pyproject.toml.
- Скрипт `scripts/black_partition.py` для исключения нечитаемых файлов.
### Изменено
- Цель `setup` в `Makefile` с прокси-безопасным fallback.
### Исправлено
- —

## [2025-09-10] - Автоформатирование кода
### Добавлено
- —
### Изменено
- Применены автоформатеры `ruff`, `isort`, `black`.
### Исправлено
- Восстановлен `scripts/fix_headers.py` после автоформатирования.

## [2025-09-10] - Фиксация версий инструментов
### Добавлено
- —
### Изменено
- Цель `setup` в `Makefile` фиксирует версии `ruff`, `black`, `isort` и `pre-commit`.
### Исправлено
- Исправлена табуляция в `Makefile` для корректного выполнения `make`.

## [2025-09-10] - Нормализация заголовков файлов
### Добавлено
- Скрипт `scripts/fix_headers.py` для очистки BOM и coding cookies.
### Изменено
- —
### Исправлено
- Заголовки Python файлов очищены от BOM и дублирующихся coding cookies.

## [2025-09-10] - Разделение конфигов Ruff и Isort
### Добавлено
- Отдельный файл `.isort.cfg` с конфигурацией.
### Изменено
- `ruff.toml` очищен от секций `isort`.
### Исправлено
- —

## [2025-09-10] - Починка импорта пакета app для тестов
### Добавлено
- —
### Изменено
- —
### Исправлено
- Добавлен `sys.path`-хак в `tests/conftest.py` для корректного импорта пакета `app`.

## [2025-09-10] - Стабилизация настроек и линтера
### Добавлено
- Функция `reset_settings_cache` и фикстура `_force_prometheus_enabled`.

### Изменено
- Обновлён `ruff.toml` и цель `lint` в `Makefile`.

### Исправлено
- —

## [2025-09-10] - Bootstrap project tooling
### Добавлено
- README.md, ARCHITECTURE.md и пример .env.
- Конфигурации pytest, mypy, ruff и Makefile.
- Смоук-скрипт и базовые тесты.
### Изменено
- —
### Исправлено
- Исправлена структура ruff.toml и обновлена секция lint.
- Интеграционный тест адаптирован под ASGITransport
- Исправлена команда smoke для корректного импорта пакета

## [2025-09-10] - Документация и чек-листы
### Добавлено
- AUDIT_REPORT.md с итогами аудита и планом действий.
- DEBT_CHECKLIST.md с перечнем технического долга.
### Изменено
- —
### Исправлено
- —

## [2025-09-10] - Sentry smoke endpoint and metrics test
### Добавлено
- Эндпоинт /__smoke__/sentry для отправки тестового события.
- Тест наличия /metrics и метрики requests_total.
### Изменено
- —
### Исправлено
- —
## [2025-09-10] - Явные заглушки CLI и обработчиков
### Добавлено
- Тест, проверяющий возвращаемую пометку в some_handler.
### Изменено
- CLI предупреждает и выбрасывает NotImplementedError для команды `retrain`.
- some_handler возвращает детерминированную заметку о незавершённых правилах.
### Исправлено
- —

## [2025-09-10] - Декомпозиция data_processor в пакет
### Добавлено
- Пакет `app/data_processor` с фасадом и модулями validators, feature_engineering, transformers и io.
### Изменено
- Обновлена архитектура в Project.md.
### Исправлено
- —

## [2025-09-10] - Заглушки ML-пайплайна
### Добавлено
- Заглушечные модули prediction_pipeline, train_base_glm, train_modifiers и retrain_scheduler.
- Тест пайплайна.
### Изменено
- —
### Исправлено
- —

## [2025-09-10] - Починка pre-commit и CI
### Добавлено
- Workflow GitHub Actions с матрицей Python и кэшем pip.
- Хуки isort и базовые pre-commit-hooks.
### Изменено
- Пин ревизий Black и Ruff с автофиксом Ruff.
### Исправлено
- —

## [2025-09-09] - Миграция конфигов на Pydantic v2
### Добавлено
- Пакет app с конфигурацией, middleware и наблюдаемостью.
- Тесты для настроек.
### Изменено
- Обновлены версии FastAPI, Uvicorn, Prometheus Client и Sentry SDK.
### Исправлено
- —

## [2025-08-24] - Интеграция Sentry и метрик
### Добавлено
- Подключён Sentry и старт Prometheus HTTP-сервера.
- Модуль метрик ECE и LogLoss с алёртом.
### Изменено
- main.py и workers/prediction_worker.py инициализируют наблюдаемость.
### Исправлено
- —

## [2025-08-24] - Описаны лиги и проверки данных
### Добавлено
- Список поддерживаемых лиг и глубина ретро в Project.md.
- Проверки обязательных колонок в services/data_processor.py.
- Уточнённые вопросы по данным в qa.md.
### Изменено
- —
### Исправлено
- —

## [2025-08-24] - Логирование времени и Redis-lock
### Добавлено
- Middleware замера времени обработчиков с логированием p95 и среднего.
- Redis-lock при генерации прогнозов.
### Изменено
- Dispatcher подключает middleware тайминга.
### Исправлено
- —

## [2025-08-25] - Расширение контроля покрытия
### Добавлено
- JSON-отчёт покрытия с информацией о пакетах и проблемных файлах.
### Изменено
- Скрипт `tools/coverage_enforce.py` поддерживает новые пороги и вывод топ-модулей.
### Исправлено
- Сообщения о нарушении порогов покрытия становятся компактными.

## [2025-08-24] - Валидация команд и rate-limit
### Добавлено
- Pydantic-модели команд (/predict, /start, /help, /terms).
- Middleware для ограничения частоты запросов.
### Изменено
- Обработчики команд используют Pydantic-валидацию.
### Исправлено
- —

## [2025-08-24] - Настроены тесты и CI
### Добавлено
- Юнит-тесты для модулей services и ml.
- Настроены pre-commit хуки (Black, Ruff, mypy).
- Workflow GitHub Actions для запуска линтеров и тестов.
### Изменено
- Обновлены зависимости для инструментов разработки.
### Исправлено
- Удалён пустой `__init__.py` в корне для корректного импорта в тестах.

## [2025-08-24] - Очистка конфликтов и обновление зависимостей
### Добавлено
- —
### Изменено
- Сведены зависимости в requirements.txt без повторов.
### Исправлено
- Удалены конфликтные маркеры в main.py и requirements.txt.

## [2025-08-23] - Рефакторинг ML-слоёв
### Добавлено
- Модули `ml/base_poisson_glm.py`, `ml/modifiers_model.py`, `ml/calibration.py`, `ml/montecarlo_simulator.py`.
- Реэкспорт PredictionModifier в `ml.modifiers_model`.
### Изменено
- RecommendationEngine получает базовую модель через DI, обновлены импорты сервисов и скриптов.
- Добавлен недостающий импорт CalibrationLayer в train_model.py.
### Исправлено
- Удалены устаревшие импорты калибрации и модификаторов.
## [2025-08-23] - Обновление структуры tasktracker
### Добавлено
- Добавлены задачи по ML-пайплайну (GLM, модификаторы, Монте-Карло) в новом формате.

### Изменено
- Переименован Tasktracker.md в tasktracker.md и удалена старая таблица задач.

### Исправлено
- —

## [2025-08-23] - Старт документации проекта
### Добавлено
- Созданы файлы: Project.md, Tasktracker.md, Diary.md, qa.md.
- Описана архитектура трёхуровневой модели и базовые стандарты разработки.

### Изменено
- —

### Исправлено
- —

## [2025-10-07] - Diagnostics v2 quality gates
### Добавлено
- Модуль `app/data_quality` с контрактами, проверками и репортингом.
- Скрипты `tools/golden_regression.py`, `tools/drift_report.py`, `tools/bench.py` и пакет `app/diagnostics`.
- Документация: `docs/quality_gates.md`, `docs/diagnostics.md`, бейдж в README.
- Тесты в `tests/diagnostics/` (data quality, golden, drift, calibration, invariance, bench).

### Изменено
- `tools/run_diagnostics.py` агрегирует новые секции (data quality, golden, drift, calibration, bench, invariance).
- `.env.example` дополнен переменными `GOLDEN_*`, `DRIFT_*`, `BENCH_*`; CI запускает диагностики v2.
- Расширены отчёты diagnostics (новые артефакты, записи в JSON/Markdown).

### Исправлено
- —
## [2025-10-12] - Diagnostics automation v2.2
### Добавлено
- Планировщик `diagtools.scheduler` с запуском `diag-run`/`diag-drift`/`golden_regression`/`bench`, историей и алертами.
- HTML-дэшборд (`diagtools.reports_html`) и хранение истории (`reports/diagnostics/history/`).
- CLI `diagtools.drift_ref_update` для подготовки drift-референсов и changelog-вставок.
- Тесты для планировщика, отчётов, истории, Chat-Ops и auto-ref-update.

### Изменено
- `diagtools.run_diagnostics` теперь генерирует HTML и обновляет историю, поддерживает `DIAG_TRIGGER`.
- Расширен README/документация (`docs/diagnostics.md`, `docs/quality_gates.md`) новыми переменными и политикой no-binaries.
- Обновлена CI-конвейер `.github/workflows/ci.yml`: job `diagnostics-scheduled`, гард `assert-no-binaries`.
- `app/bot` получил команды `/diag` (`last|drift|link`) и метрики `diag_runs_total`, `diag_last_status`.

### Исправлено
- Синхронизация `.env.example` и `config.Settings` новыми флагами диагностики/алертов.
- `.gitignore` покрывает runtime-артефакты (`reports/`, `data/`, бинарные форматы).

## [2025-10-20] - Value calibration gate
### Добавлено
- GitHub Actions job `value-calibration-gate`, запускающий `python -m diagtools.value_check --calibrate --days ${BACKTEST_DAYS}` и выгружающий `value_calibration.{json,md}` как артефакты.
- Кэширование результатов калибровки (`value_calibration.json`/`.md`) в `diagtools.value_check` с флагом `--calibrate` для форсированного прогона.
- Обновление `docs/Project.md`/`docs/diagnostics.md` описанием модулей `app/value_calibration`, `app/value_alerts` и поведения CLI.

### Изменено
- `diagtools.value_check` использует настройки `BACKTEST_DAYS`, берёт отчёт из кэша и запускает бэктест только по требованию.
- `diagtools.run_diagnostics` передаёт `BACKTEST_DAYS` в секцию Value Calibration и добавляет отчёт в JSON/Markdown-вывод.
- README дополнен бейджем «Value calibration gated ✓», `.github/workflows/ci.yml` синхронизирован по env `BACKTEST_DAYS`.

### Исправлено
- Исключена немотивированная загрузка калибровки в `diagtools.value_check` при наличии актуального отчёта.
- CI получает детерминированный отчёт value calibration даже в оффлайн-окружении (`ODDS_PROVIDER=csv`).
## [2025-09-26] - Makefile lint/test alignment
### Добавлено
- —

### Изменено
- Упрощены цели `lint`, `fmt`, `test`, `check` в `Makefile`, чтобы использовать стандартные команды и последовательный запуск `check`.
- Добавлены объявления `.PHONY` для основных автоматизационных целей `Makefile`.

### Исправлено
- Устранены ошибки `make` из-за отсутствующих табуляций в рецептах и стабилизирован вызов `make check`.
