## Задача: QA-min офлайн профиль
- **Статус**: Завершена
- **Описание**: Подготовить минимальный офлайн-профиль зависимостей для FastAPI и автоматизировать установку/self-test без изменения бизнес-кода.
- **Шаги выполнения**:
  - [x] Создан файл `requirements-qa-min.txt` с лёгким стеком FastAPI.
  - [x] Добавлены скрипты `tools/qa_deps_sync.py` и `tools/api_selftest.py` с офлайн-логикой установки и self-test.
  - [x] Обновлён `Makefile` (цели `qa-deps`, `api-selftest`) и README с разделом «QA-min offline».
- **Зависимости**: requirements-qa-min.txt, tools/qa_deps_sync.py, tools/api_selftest.py, Makefile, README.md, docs/changelog.md, docs/tasktracker.md

## Задача: Нормализация комментариев миграции 20241005_004
- **Статус**: Завершена
- **Описание**: Привести заголовок миграции `20241005_004_value_v1_4` к валидному Python-комментарию и подтвердить отсутствие синтаксических ошибок.
- **Шаги выполнения**:
  - [x] Проверено отсутствие дополнительных инструкций и актуальность документации.
  - [x] Заменён C-стиль комментариев на Python docstring в миграции.
  - [x] Запущены `python -m compileall` и `ruff` с критичными правилами.
- **Зависимости**: database/migrations/versions/20241005_004_value_v1_4.py, docs/changelog.md, docs/tasktracker.md

## Задача: Канареечный режим API
- **Статус**: Завершена
- **Описание**: Добавить канареечный флаг и инструкции раскатки без изменения бизнес-логики.
- **Шаги выполнения**:
  - [x] Добавлен флаг `CANARY` в конфигурацию, warmup-эндпоинт `/__smoke__/warmup` и Makefile-таргет `warmup`.
  - [x] API (`/`, `/healthz`, `/readyz`) и логи/метрики метят канареечный режим, фоновые задачи/воркеры завершаются ранним выходом.
  - [x] Диагностические алерты ограничены админ-чатами в канарейке, README и CI дополнены инструкциями/шагом `canary-smoke`.
- **Зависимости**: config.py, app/api.py, app/main.py, workers/prediction_worker.py, diagtools/scheduler.py, Makefile, .github/workflows/ci.yml, README.md, docs/changelog.md, docs/tasktracker.md

## Задача: Мониторинг и runbook для SportMonks/odds
- **Статус**: Завершена
- **Описание**: Добавить Prometheus-алёрты, пример переменных и краткий runbook без изменений бизнес-логики.
- **Шаги выполнения**:
  - [x] Создан `monitoring/alerts.yaml` с правилами Data Freshness, ETL, Worker Deadman, Odds stalled и API readiness.
  - [x] Добавлен `.env.alerts.example` с порогами `SM_FRESHNESS_*`, `WORKER_DEADMAN_SEC`.
  - [x] Обновлены README (Monitoring & Alerts), docs/runbook.md и Makefile/CI (`alerts-validate`).
- **Зависимости**: monitoring/alerts.yaml, .env.alerts.example, README.md, docs/runbook.md, Makefile, .github/workflows/ci.yml, docs/changelog.md, docs/tasktracker.md

## Задача: Preflight-гейт для ролей Amvera
- **Статус**: Завершена
- **Описание**: Включить опциональный строгий preflight для ролей `api`/`worker` и зафиксировать его в документации.
- **Шаги выполнения**:
  - [x] Реализован скрипт `scripts/preflight.py` с режимами `strict`/`health` и логированием результата.
  - [x] Добавлен условный вызов `python -m scripts.preflight --mode strict` в `amvera.yaml` при `PRESTART_PREFLIGHT=1`.
  - [x] Обновлены README, changelog и tasktracker, добавлены тесты `tests/scripts/test_preflight.py`.
- **Зависимости**: scripts/preflight.py, amvera.yaml, README.md, docs/changelog.md, docs/tasktracker.md, tests/scripts/test_preflight.py

## Задача: Унификация health/readiness для Amvera API
- **Статус**: Завершена
- **Описание**: Перевести проверки живости на `/healthz`/`/readyz`, унифицировать контракт переменных окружения и обновить документацию.
- **Шаги выполнения**:
  - [x] Реализованы эндпоинты `/healthz` и `/readyz` в `app/api.py` с проверками PostgreSQL, Redis и runtime-флагов.
  - [x] Добавлены fallback-поля и предупреждения о депрекации в `app/config.py`, обновлён `.env.example`.
  - [x] Обновлены smoke/интеграционные тесты и `scripts/verify.py` для использования `app.api:app` и новых алиасов.
  - [x] Синхронизированы `README.md`, `docs/deploy-amvera.md`, `amvera.yaml` и changelog/tasktracker.
  - [x] Offline-режим pytest больше не пропускает проверки `/healthz` и `/readyz`.
- **Зависимости**: app/api.py, app/config.py, app/main.py, README.md, docs/deploy-amvera.md, docs/changelog.md, docs/tasktracker.md, .env.example, tests/*, scripts/verify.py

## Задача: Подготовка деплоя на Amvera
- **Статус**: Завершена
- **Описание**: Настроить конфигурацию Amvera для API, фонового воркера и Telegram-бота без изменения бизнес-логики.
- **Шаги выполнения**:
  - [x] Обновлён `amvera.yaml` с выбором ролей и единым скриптом запуска.
  - [x] Добавлен пример окружения `.env.amvera.example` с placeholders.
  - [x] Реализованы точки входа `app/api.py`, `scripts/worker.py`, `scripts/tg_bot.py`.
  - [x] Настройки БД и Redis вынесены в `app/config.py` (DSN rw/ro/rr, `REDIS_URL`).
  - [x] README дополнен разделом «Deploy to Amvera», обновлены changelog/tasktracker.
- **Зависимости**: amvera.yaml, .env.amvera.example, app/config.py, app/api.py, scripts/worker.py, scripts/tg_bot.py, README.md, docs/changelog.md, docs/tasktracker.md

## Задача: Обновление lint и форматирования
- **Статус**: Завершена
- **Описание**: Перенастроить make-цели для мягкого/строгого линта, добавить проверку изменённых файлов и синхронизировать конфиги форматирования.
- **Шаги выполнения**:
  - [x] Обновлён `lint-soft`, чтобы запускать только критичные правила Ruff и оставаться alias-ом для `lint`.
  - [x] Добавлена цель `lint-changed`, проверяющая изменённые Python-файлы с критичными правилами.
  - [x] Цель `check` вызывает `make lint` и `make test` последовательно.
  - [x] Обновлены настройки Black/isort (Python 3.10, длина строки 88, include/skip) в `pyproject.toml`.
  - [x] Устранены критичные предупреждения Ruff `F821` в `app/data_providers/sportmonks/provider.py` и `app/lines/aggregator.py`.
  - [x] Задокументированы изменения в `docs/changelog.md`.
- **Зависимости**: Makefile, pyproject.toml, app/data_providers/sportmonks/provider.py, app/lines/aggregator.py, docs/changelog.md, docs/tasktracker.md


## Задача: Разделение мягкого и строгого Ruff
- **Статус**: Завершена
- **Описание**: Настроить мягкий режим Ruff для `make check`, сохраняя возможность включить строгие проверки позже.
- **Шаги выполнения**:
  - [x] Добавлены цели `lint-soft` и `lint-strict`, а `lint` перенаправлен на мягкий режим.
  - [x] Обновлена цель `fmt`, чтобы запускать `ruff check . --fix` перед `isort` и `black`.
  - [x] Сконфигурирован Ruff в `pyproject.toml` (версия, длина строки, исключения, правила, per-file ignores).
- **Зависимости**: Makefile, pyproject.toml, docs/changelog.md, docs/tasktracker.md

## Задача: SportMonks ingestion v3
- **Статус**: Завершена
- **Описание**: Реализовать устойчивый сбор данных SportMonks v3 с кэшем, БД и сервисными скриптами для прогнозов/оддсов.
- **Шаги выполнения**:
  - [x] Создан пакет `sportmonks/{client.py,endpoints.py,cache.py,repository.py,schemas.py}` и сервис `services/feature_builder.py`.
  - [x] Добавлены скрипты `scripts/update_upcoming.py` (cron ingest + симуляция) и `scripts/get_match_prediction.py` (CLI explain).
  - [x] Расширен `config.py` TTL профилями, обновлены `docs/Project.md`, README (curl-примеры), `docs/changelog.md` и Tasktracker.
  - [x] Написаны тесты `tests/sm/test_sportmonks_client_v3.py` для пагинации, ретраев и парсинга lineups/xGFixture.
- **Зависимости**: sportmonks/{__init__.py,client.py,endpoints.py,cache.py,repository.py,schemas.py}, services/feature_builder.py, scripts/{update_upcoming.py,get_match_prediction.py}, config.py, docs/{Project.md,changelog.md,tasktracker.md}, README.md, tests/sm/test_sportmonks_client_v3.py

## Задача: Offline QA stubs & CI gate
- **Статус**: Завершена
- **Описание**: Обеспечить прохождение `pytest -q` без тяжёлых зависимостей через стабы и отдельный CI-профиль.
- **Шаги выполнения**:
  - [x] Добавлены стабы `tests/_stubs/{numpy.py,pandas.py,sqlalchemy.py,joblib.py}` и поддержка одиночных модулей/переменной `USE_OFFLINE_STUBS` в загрузчике.
  - [x] Обновлён `tests/conftest.py` для регистрации новых стабов и принудительного режима через `USE_OFFLINE_STUBS`.
  - [x] Переведены `diagtools.{drift,run_diagnostics,golden_regression}` на ленивые импорты `numpy/pandas`.
  - [x] Обновлены README, `docs/dev_guide.md`, `docs/changelog.md`, `docs/tasktracker.md` и CI (`.github/workflows/ci.yml`) новым job `offline-qa`.
- **Зависимости**: tests/_stubs/{__init__.py,numpy.py,pandas.py,sqlalchemy.py,joblib.py}, tests/conftest.py, diagtools/{drift/__init__.py,run_diagnostics.py,golden_regression.py}, README.md, docs/{dev_guide.md,changelog.md,tasktracker.md}, .github/workflows/ci.yml

## Задача: Value v1.5 best-price & settlement
- **Статус**: Завершена
- **Описание**: Завершить best-price роутинг с учётом надёжности/аномалий, внедрить автоматический сеттлмент и обновить диагностику/документацию.
- **Шаги выполнения**:
  - [x] Реализованы `app/lines/reliability.py`, `app/lines/anomaly.py`, `app/settlement/engine.py`, обновлены `app/lines/aggregator.py`, `app/value_service.py`, `app/value_clv.py` и леджер (`database/schema.sql`, миграция `20241007_005_value_v1_5.py`).
  - [x] Расширены бот-UX и форматирование (`app/bot/formatting.py`, `app/bot/keyboards.py`, `app/bot/routers/{commands,callbacks}.py`) блоком «Best price» и пояснением провайдера.
  - [x] Диагностика (`diagtools/run_diagnostics.py`) и новые CLI (`diagtools/provider_quality.py`, `diagtools/settlement_check.py`) добавлены в CI, обновлены README, docs (`dev_guide.md`, `user_guide.md`, `diagnostics.md`, `Project.md`).
  - [x] Написать и прогнать тесты (`tests/odds/*`, `tests/value/test_settlement_engine.py`, `tests/bot/test_portfolio_extended.py`, `tests/diag/*`); `pytest -q` проходит оффлайн благодаря новым стабам.
- **Зависимости**: app/lines/{aggregator.py,reliability.py,anomaly.py}, app/settlement/engine.py, app/value_{service.py,clv.py}, app/bot/{formatting.py,keyboards.py,routers/commands.py,routers/callbacks.py}, config.py, database/schema.sql, database/migrations/versions/20241007_005_value_v1_5.py, diagtools/{run_diagnostics.py,provider_quality.py,settlement_check.py}, README, docs/{dev_guide.md,user_guide.md,diagnostics.md,Project.md,changelog.md,tasktracker.md}, tests/{odds/test_reliability.py,odds/test_best_route.py,odds/test_anomaly_filter.py,value/test_settlement_engine.py,bot/test_portfolio_extended.py,diag/test_provider_quality.py,diag/test_settlement_check.py}.

## Задача: Value v1.4 audit & rollout
- **Статус**: Завершена
- **Описание**: Внедрить мультипровайдерный агрегатор, расчёт CLV и обновить UX/диагностику согласно Value v1.4.
- **Шаги выполнения**:
  - [x] Реализованы `app/lines/aggregator.py`, `app/lines/movement.py`, `app/value_clv.py`, миграция `20241005_004_value_v1_4` и обновление `database/schema.sql`.
  - [x] Обновлены `app/value_service.py`, `app/bot/{formatting.py,keyboards.py,routers/commands.py,routers/callbacks.py}` для consensus-трендов, кнопки «Провайдеры» и `/portfolio`.
  - [x] Добавлены CLI/диагностика (`diagtools/clv_check.py`, расширение `diagtools/run_diagnostics.py`, job `value-agg-clv-gate` в `.github/workflows/ci.yml`).
  - [x] Созданы тесты (`tests/odds/test_aggregator_basic.py`, `tests/odds/test_movement_closing.py`, `tests/value/test_clv_math.py`, `tests/bot/test_portfolio_and_providers.py`, `tests/diag/test_clv_check.py`) и фикстуры `tests/fixtures/odds_multi/*.csv`.
  - [x] Обновлены `.env.example`, README, docs (`dev_guide.md`, `user_guide.md`, `diagnostics.md`, `Project.md`), changelog и статус `docs/status/value_v1_4_audit.md`.
- **Зависимости**: app/lines/{aggregator.py,movement.py,storage.py}, app/value_{service.py,clv.py}, app/bot/{formatting.py,keyboards.py,routers/commands.py,routers/callbacks.py}, config.py, database/schema.sql, database/migrations/versions/20241005_004_value_v1_4.py, diagtools/{run_diagnostics.py,value_check.py,clv_check.py}, .github/workflows/ci.yml, .env.example, README.md, docs/{dev_guide.md,user_guide.md,diagnostics.md,Project.md,changelog.md,status/value_v1_4_audit.md,tasktracker.md}, tests/{odds/test_aggregator_basic.py,odds/test_movement_closing.py,value/test_clv_math.py,bot/test_portfolio_and_providers.py,diag/test_clv_check.py}, tests/fixtures/odds_multi/*.csv.

## Задача: Value calibration gate
- **Статус**: Завершена
- **Описание**: Добавить CI-гейт для value-калибровки, кеширование отчётов и документацию по новым секциям.
- **Шаги выполнения**:
  - [x] Обновлён `diagtools.value_check` (кэш отчёта, `--calibrate`, `BACKTEST_DAYS`).
  - [x] Обновлён `diagtools.run_diagnostics` и документация (`docs/Project.md`, `docs/diagnostics.md`).
  - [x] Добавлен job `value-calibration-gate` и бейдж в README.
- **Зависимости**: diagtools/value_check.py, diagtools/run_diagnostics.py, .github/workflows/ci.yml, README.md, docs/Project.md, docs/diagnostics.md, docs/changelog.md, docs/tasktracker.md

## Задача: Value odds integration & bot UX
- **Статус**: Завершена
- **Описание**: Подключить провайдеры котировок (CSV/HTTP), нормализовать overround, вычислять value-кейсы и отобразить их в боте/диагностике.
- **Шаги выполнения**:
  - [x] Реализован пакет `app.lines` (mapper, CSV/HTTP провайдеры, SQLite-хранилище odds_snapshots и миграция).
  - [x] Добавлены `app/pricing/overround.py`, `app/value_detector.py`, `app/value_service.py`, счётчики Prometheus и Value-CLI `diagtools/value_check.py`.
  - [x] Расширены команды `/value`, `/compare`, `/alerts`, форматирование карточек, хранение предпочтений (`value_alerts`).
  - [x] Обновлены `diagtools/run_diagnostics.py` (секция Value & Odds), `.env.example`, README, docs/user_guide.md, docs/dev_guide.md, docs/Project.md, changelog/tasktracker и тесты (`tests/odds/*`, `tests/bot/test_value_commands.py`, `tests/diag/test_value_check.py`).
- **Зависимости**: app/lines/*, app/pricing/overround.py, app/value_detector.py, app/value_service.py, app/bot/{formatting.py,routers/commands.py,storage.py}, app/metrics.py, config.py, .env.example, database/schema.sql, database/migrations/versions/20240917_003_add_odds_snapshots.py, diagtools/run_diagnostics.py, diagtools/value_check.py, README.md, docs/{user_guide.md,dev_guide.md,Project.md,changelog.md,tasktracker.md}, tests/{odds/*,bot/test_value_commands.py,diag/test_value_check.py}.

## Задача: Stub isolation & SportMonks ETag key hardening
- **Статус**: Завершена
- **Описание**: Изолировать оффлайн-заглушки тестов и усилить канонизацию ETag-кэша SportMonks по методу/пути/allowlist.
- **Шаги выполнения**:
  - [x] Перенесены stubs `pydantic/httpx/aiogram/prometheus_client/redis/rq` в `tests/_stubs` и добавлен загрузчик `ensure_stubs`.
  - [x] Обновлён `tests/conftest.py` для ленивого подключения заглушек и инициализации окружения.
  - [x] Расширен `SportmonksETagCache` каноническими ключами, TTL-страховкой и тестами `tests/sm/test_etag_cache.py`.
- **Зависимости**: tests/_stubs/*, tests/conftest.py, app/data_providers/sportmonks/{cache.py,provider.py}, tests/sm/test_etag_cache.py, docs/changelog.md, docs/tasktracker.md

## Задача: SportMonks offline QA hardening
- **Статус**: Завершена
- **Описание**: Обеспечить оффлайн-тестирование SportMonks, ETag-кеш, отчёты по свежести и автоматические гейты.
- **Шаги выполнения**:
  - [x] Добавлены фикстуры `tests/fixtures/sm/*.json`, dry-run для `scripts/sm_sync.py` и CSV отчёт по коллизиям команд.
  - [x] Реализован `SportmonksETagCache`, фильтрация allowlist и расширенный `SportmonksProvider`/ботовые бейджи.
  - [x] Добавлены тесты (`tests/sm/test_*`, `tests/model/test_features_ingestion.py`, `tests/bot/test_staleness_badges.py`, `tests/ops/test_freshness_gate.py`).
  - [x] CLI `diagtools.freshness`, секция лиг в отчётах и обновлённые README/diagnostics/.env.example/changelog/tasktracker.
- **Зависимости**: scripts/sm_sync.py, app/data_providers/sportmonks/{cache.py,provider.py,schemas.py}, app/bot/routers/commands.py, diagtools/freshness.py, diagtools/run_diagnostics.py, tests/sm/*, tests/model/test_features_ingestion.py, tests/bot/test_staleness_badges.py, tests/ops/test_freshness_gate.py, docs/diagnostics.md, README, .env.example, docs/changelog.md, docs/tasktracker.md.

## Задача: Offline dependency stubs for SportMonks QA
- **Статус**: Завершена
- **Описание**: Заменить недостающие зависимости (pydantic/httpx/aiogram/prometheus_client/redis/rq) текстовыми заглушками и адаптировать тесты к оффлайн-режиму.
- **Шаги выполнения**:
  - [x] Добавлены stubs `pydantic`, `pydantic_settings`, `httpx`, `prometheus_client`, `aiogram`, `redis`, `rq` с необходимыми интерфейсами.
  - [x] Расширен `tests/conftest.py` для поддержки async-тестов без pytest-asyncio и обновлены билдеры клавиатур aiogram.
  - [x] Ужесточён парсинг матчей (`SportmonksProvider`), ключи ETag и фиксация данных свежести в тестах.
- **Зависимости**: pydantic/*, pydantic_settings/*, httpx/*, prometheus_client/*, aiogram/*, redis/*, rq/*, app/bot/services.py, app/data_providers/sportmonks/{provider.py,cache.py}, tests/{conftest.py,ops/test_freshness_gate.py}, docs/changelog.md, docs/tasktracker.md.

## Задача: SportMonks Integrator v1
- **Статус**: Завершена
- **Описание**: Добавить SportMonks ETL/клиент, кэш, мэппинг, свежесть данных и интеграцию в бота.
- **Шаги выполнения**:
  - [x] Реализован пакет `app/data_providers/sportmonks` (client/provider/repository/metrics).
  - [x] Добавлены таблицы `sm_*`, `map_*`, CLI `scripts/sm_sync.py` и миграция.
  - [x] Обновлены бот (`SportmonksDataSource`, бейджи свежести), планировщик и диагностика Data Freshness.
  - [x] Расширены документация (.env, README, changelog/tasktracker) и тесты (`tests/sm/*`, `tests/bot/test_staleness_badges.py`).
- **Зависимости**: app/data_providers/sportmonks/*, app/data_source.py, scripts/sm_sync.py, workers/retrain_scheduler.py, app/bot/*,
  diagtools/run_diagnostics.py, database/migrations/versions/20240917_002_add_sportmonks_tables.py, database/schema.sql,
  .env.example, README.md, docs/changelog.md, docs/tasktracker.md, tests/sm/*, tests/bot/test_staleness_badges.py,
  tests/model/test_features_from_sm.py

## Задача: Diagnostics v2.2 — Continuous monitoring & Chat-Ops
- **Статус**: Завершена
- **Описание**: Включить автоматический запуск диагностики, HTML-дэшборд, Chat-Ops и защиту от бинарников в PR.
- **Шаги выполнения**:
  - [x] Добавлен планировщик `diagtools/scheduler.py` с поддержкой CRON/ручных запусков, алертов и метрик.
  - [x] Реализован `diagtools/reports_html.py` (HTML + история) и интеграция в `diagtools.run_diagnostics`.
  - [x] Добавлен CLI `diagtools.drift_ref_update.py` и обновлены ENV (`DIAG_*`, `ALERTS_*`, `AUTO_REF_UPDATE`).
  - [x] Расширен бот (команды `/diag`, история, drift-only, выдача HTML) и тесты для Chat-Ops/diagtools.
  - [x] Обновлены `.env.example`, `config.py`, `README.md`, `docs/diagnostics.md`, `docs/quality_gates.md`, `.gitignore`.
  - [x] Обновлена CI (`diagnostics-scheduled`, `assert-no-binaries`, публикация HTML/истории) и документация (changelog/tasktracker).
- **Зависимости**: diagtools/scheduler.py, diagtools/reports_html.py, diagtools/drift_ref_update.py, diagtools/run_diagnostics.py, app/bot/routers/commands.py, metrics/metrics.py, .env.example, config.py, README.md, docs/diagnostics.md, docs/quality_gates.md, docs/changelog.md, docs/tasktracker.md, .gitignore, .github/workflows/ci.yml, tools/ci_assert_no_binaries.sh, tests/diagtools/*, tests/bot/test_chatops_diag.py

## Задача: Diagnostics v2.1 — Drift packaging & CI gate
- **Статус**: Завершена
- **Описание**: Перевести инструменты диагностики в пакет `diagtools`, усилить дрифт-отчёты (стратификация, окна, пороги) и включить CI-гейт с артефактами.
- **Шаги выполнения**:
  - [x] Перенесены CLI (`run_diagnostics`, `bench`, `golden_regression`, `drift`) в пакет `diagtools` и добавлены entrypoints `diag-run`/`diag-drift`.
  - [x] Реализован `diagtools.drift` с PSI/KS по global/league/season, генерацией Markdown/JSON/CSV/PNG и reference parquet + meta.
  - [x] Обновлены `diagtools.run_diagnostics`, Prometheus-метрики и Makefile/README под новые ENV (`DRIFT_ROLLING_DAYS`, `DRIFT_KS_P_*`).
  - [x] Добавлены GitHub Actions job `diagnostics-drift`, .env параметры и CI-команды с использованием `diagtools`.
  - [x] Написаны тесты `tests/diagnostics/test_drift_packaging|strata|thresholds|artifacts.py`.
- **Зависимости**: diagtools/*, tests/diagnostics/test_drift_*.py, tests/diagnostics/test_bench_smoke.py, tests/diagnostics/test_golden.py, metrics/metrics.py, pyproject.toml, requirements.txt, requirements.lock, Makefile, .github/workflows/ci.yml, README.md, docs/diagnostics.md, docs/changelog.md, docs/tasktracker.md, CHANGELOG.md, .env.example

## Задача: Diagnostics drift_report import hotfix
- **Статус**: Завершена
- **Описание**: Исправить падение `tools/drift_report.py` при запуске напрямую из корня репозитория из-за отсутствия пути проекта в `sys.path`.
- **Шаги выполнения**:
  - [x] Воспроизведён `ModuleNotFoundError` на `tools.golden_regression` при запуске `python tools/drift_report.py`.
  - [x] Добавлено подключение корня репозитория к `sys.path` внутри `tools/drift_report.py` перед импортами.
  - [x] Прогнан `python tools/drift_report.py --reports-dir reports/diagnostics/drift --ref-days 90` и подтверждена генерация отчётов.
  - [x] Обновлены `docs/changelog.md` и `docs/tasktracker.md`.
- **Зависимости**: tools/drift_report.py, docs/changelog.md, docs/tasktracker.md

## Задача: Diagnostics automation & ops sanity
- **Статус**: Завершена
- **Описание**: Автоматизировать сбор сквозной диагностики (ENV/модели/бот/Ops) и устранить блокирующие синтаксические ошибки.
- **Шаги выполнения**:
  - [x] Реализован скрипт `tools/run_diagnostics.py` с генерацией отчетов/логов в `reports/diagnostics`.
  - [x] Прогнан smoke `python -m main --dry-run`, собраны логи pytest и сводка статусов.
  - [x] Исправлены ошибки индентации `telegram/bot.py` и заголовка `telegram/utils/token_bucket.py`.
  - [x] Обновлены `docs/changelog.md`, `docs/tasktracker.md`.
- **Зависимости**: tools/run_diagnostics.py, reports/diagnostics/*, telegram/bot.py, telegram/utils/token_bucket.py, docs/changelog.md, docs/tasktracker.md

## Задача: Product v1 — Predictions UX rollout
- **Статус**: Завершена
- **Описание**: Выпустить продакшн-набор команд Telegram-бота с объяснимостью, ежедневными дайджестами, кешем и экспортом.
- **Шаги выполнения**:
  - [x] Реализованы модули `app/bot/*` (кеширование, форматирование, сервисы, SQLite, inline-клавиатуры).
  - [x] Добавлены роутеры `/today`, `/match`, `/explain`, `/league`, `/subscribe`, `/settings`, `/export`, `/about`, `/admin`.
  - [x] Обновлены конфиги и документация (`config.py`, `.env.example`, README, docs/user_guide.md, docs/dev_guide.md, docs/Project.md`).
  - [x] Реализованы экспорт CSV/PNG, таблицы `user_prefs`, `subscriptions`, `reports`, метрики `render_latency_seconds`, `bot_digest_sent_total`.
  - [x] Написаны тесты `tests/bot/*`, расширен контракт ENV и changelog/tasktracker.
- **Зависимости**: app/bot/*, telegram/handlers/__init__.py, config.py, requirements.txt, requirements.lock, database/schema.sql, README, docs/*, tests/bot/*, docs/changelog.md, docs/tasktracker.md, .env.example, app/metrics.py

## Задача: Hardening Pack v1
- **Статус**: Завершена
- **Описание**: Обеспечить единственный инстанс, graceful shutdown, health-probe и контракт окружения.
- **Шаги выполнения**:
  - [x] Добавлены `app/runtime_lock.py`, health-сервер и универсальный `retry_async`.
  - [x] Обновлены `main.py`, `telegram/bot.py`, `logger.py`, `.env.example`, `amvera.yaml` и CI smoke.
  - [x] Дополнена документация (`README.md`, `docs/deploy-amvera.md`) и введены тесты (`tests/test_runtime_lock.py`, `tests/test_env_contract.py`, `tests/test_data_paths.py`).
  - [x] Протоколированы изменения в changelog и tasktracker.
- **Зависимости**: main.py, telegram/bot.py, logger.py, app/runtime_lock.py, app/health.py, app/utils/retry.py, .env.example, amvera.yaml, docs/deploy-amvera.md, README.md, docs/changelog.md, .github/workflows/ci.yml, tests/test_runtime_lock.py, tests/test_env_contract.py, tests/test_data_paths.py, docs/tasktracker.md

## Задача: Amvera Ops v2 readiness & maintenance
- **Статус**: Завершена
- **Описание**: Развести `/health` и `/ready`, включить метрики по фичефлагам, настроить резервное копирование SQLite и обновить документацию.
- **Шаги выполнения**:
  - [x] Добавлен `RuntimeState` и readiness-проба `/ready` в health-сервер.
  - [x] Реализованы новые метрики, токен-бакет и идемпотентность команд бота.
  - [x] Настроены PRAGMA, ежедневные бэкапы и недельный `VACUUM/ANALYZE`.
  - [x] Обновлены README, docs/deploy-amvera.md, `.env.example`, changelog и tasktracker.
  - [x] Добавлены тесты (`tests/test_readiness.py`, `tests/test_db_maintenance.py`, `tests/test_metrics_server.py`, `tests/test_runtime_lock_stale.py`).
- **Зависимости**: main.py, app/health.py, app/runtime_state.py, app/runtime_lock.py, app/db_maintenance.py, app/metrics.py, telegram/bot.py, telegram/middlewares.py, workers/task_manager.py, storage/persistence.py, docs/*, tests/*

## Задача: Amvera — подготовка к деплою
- **Статус**: В процессе
- **Описание**: Перевести бот на требования Amvera: хранить данные в `/data`, добавить `amvera.yaml`, smoke-проверку и документацию.
- **Шаги выполнения**:
  - [x] Обновлены настройки и код для чтения путей из `DB_PATH`/`REPORTS_DIR`/`MODEL_REGISTRY_PATH`/`LOG_DIR` с дефолтом `/data`.
  - [x] Добавлен `--dry-run` и задержка `BOT_STARTUP_DELAY` перед запуском polling.
  - [x] Добавлены `amvera.yaml`, документация и GitHub Actions job `amvera-smoke`.
  - [ ] Выполнить деплой на Amvera и smoke-проверку в боевом окружении.
- **Зависимости**: amvera.yaml, README.md, docs/deploy-amvera.md, main.py, telegram/bot.py, storage/persistence.py, .github/workflows/ci.yml

## Задача: E6.18 — Prediction worker dirty payload coverage
- **Статус**: Завершена
- **Описание**: Расширить негативные тесты воркера предсказаний: маскирование ошибок ядра, таймаут Redis-lock и валидацию «грязного» payload (NaN/negative).
- **Шаги выполнения**:
  - [x] Обновлён тестовый double `SpyPredictor` валидатором, имитирующим проверку входных данных без утечки секретов.
  - [x] Подтверждён контролируемый статус job при таймауте Redis-lock и отсутствие повторного запуска.
  - [x] Параметризованы сценарии «грязного» payload (NaN/negative) и обновлена документация.
- **Зависимости**: tests/workers/test_prediction_worker_errors.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.17 — Redis factory retry coverage
- **Статус**: Завершена
- **Описание**: Зафиксировать повторные попытки RedisFactory с экспоненциальным backoff, jitter и маскировкой DSN.
- **Шаги выполнения**:
  - [x] Добавлены тесты backoff и jitter `tests/database/test_redis_factory_backoff.py` с контролем задержек и логов.
  - [x] Расширен `workers/redis_factory.RedisFactory` параметрами повторных попыток и безопасным логированием.
  - [x] Обновлены записи changelog/tasktracker для задачи E6.17.
- **Зависимости**: workers/redis_factory.py, tests/database/test_redis_factory_backoff.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.16 — Prediction worker log hardening
- **Статус**: Завершена
- **Описание**: Уточнить негативные тесты воркера предсказаний, зафиксировать маскирование логов и контроль таймаутов
  Redis-lock.
- **Шаги выполнения**:
  - [x] Добавлен логирующий double очереди для проверки сообщений без секретов.
  - [x] Подтверждён единичный запуск job при таймауте Redis-lock и возврат контролируемой ошибки.
  - [x] Проведена валидация «грязного» payload (отрицательный `n_sims`) и обновлена документация.
- **Зависимости**: tests/workers/test_prediction_worker_errors.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.15 — Queue adapter edge coverage
- **Статус**: Завершена
- **Описание**: Добавить edge-тесты очереди для маппинга редких статусов RQ и маскировки ошибок enqueue/status/cancel.
- **Шаги выполнения**:
  - [x] Покрыт маппинг статусов с учётом регистра и пробелов, включая дефолт при отсутствии статуса.
  - [x] Смоделированы исключения Redis/RQ без сетевых вызовов через моки очереди.
  - [x] Зафиксированы изменения в changelog и tasktracker.
- **Зависимости**: tests/workers/test_queue_adapter_edges.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.14 — Makefile coverage pipeline cleanup
- **Статус**: Завершена
- **Описание**: Упростить цели покрытия, объединив контроль порогов и генерацию отчётов без предварительного удаления артефактов.
- **Шаги выполнения**:
  - [x] Обновлена цель `test-all` с последовательным запуском pytest и `tools.coverage_enforce`.
  - [x] Перенастроена цель `coverage-html` на сквозной пайплайн pytest → enforcement → html-отчёт.
  - [x] Зафиксированы изменения в документации changelog/tasktracker.
- **Зависимости**: Makefile, docs/changelog.md, docs/tasktracker.md

## Задача: E6.13 — Coverage gaps script trim
- **Статус**: Завершена
- **Описание**: Сократить и стабилизировать скрипт генерации отчёта coverage gaps по результатам ревью.
- **Шаги выполнения**:
  - [x] Удалён досрочный `return` из обхода классов и сохранена фильтрация по целевым пакетам.
  - [x] Сохранён формат Markdown-отчёта с диапазонами пропущенных строк.
  - [x] Сокращён модуль до требуемого лимита в 200 строк и обновлена документация.
- **Зависимости**: tools/coverage_gaps.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.12 — Coverage gaps top-20 refresh
- **Статус**: Завершена
- **Описание**: Переписать генерацию отчёта coverage gaps под единый ТОП-20 файлов и актуализировать документацию.
- **Шаги выполнения**:
  - [x] Обновлён разбор `coverage.xml` с фильтрацией пакетов и перерасчётом процента покрытия по строкам.
  - [x] Пересобран Markdown-отчёт `reports/coverage_gaps.md` с диапазонами пропущенных строк и автоматическим созданием каталога.
  - [x] Зафиксированы изменения в changelog и tasktracker.
- **Зависимости**: tools/coverage_gaps.py, reports/coverage_gaps.md, docs/changelog.md, docs/tasktracker.md

## Задача: E6.11 — Coverage enforcement parser tweaks
- **Статус**: Завершена
- **Описание**: Уточнить расчёт пропущенных строк в Cobertura и привести сообщение об ошибке к краткому формату.
- **Шаги выполнения**:
  - [x] Ограничен разбор строк покрытия прямыми элементами `<line>` внутри секции `<lines>`.
  - [x] Сокращено сообщение о провале порогов до формата «coverage check failed».
  - [x] Зафиксированы обновления в changelog и tasktracker.
- **Зависимости**: tools/coverage_enforce.py, docs/changelog.md, docs/tasktracker.md

## Задача: E6.10 — Актуализация exclude_lines coverage
- **Статус**: Завершена
- **Описание**: Привести правило `exclude_lines` в `.coveragerc` к унифицированному шаблону блока запуска.
- **Шаги выполнения**:
  - [x] Обновлено условие `if __name__ == .__main__.:` в списке исключений отчёта покрытия.
  - [x] Задокументированы изменения в changelog с привязкой к задаче.
- **Зависимости**: .coveragerc, docs/changelog.md

## Задача: E6.8 — Coverage omit refresh
- **Статус**: Завершена
- **Описание**: Согласовать список исключений coverage, удалив точечное правило `scripts/entrypoint.sh` в пользу шаблона.
- **Шаги выполнения**:
  - [x] Пересмотрен блок `omit` в `.coveragerc` и устранено дублирование записей скриптов.
  - [x] Зафиксированы обновления в `docs/changelog.md` и `docs/tasktracker.md`.
  - [x] Проверено отсутствие дополнительных требований к конфигурации покрытия.
- **Зависимости**: .coveragerc, docs/changelog.md, docs/tasktracker.md

## Задача: DB router fallback coverage
- **Статус**: Завершена
- **Описание**: Покрыть fallback чтения и негативные сценарии DBRouter отдельными тестами.
- **Шаги выполнения**:
  - [x] Смоделирован пустой `DATABASE_URL_RO`, подтверждён fallback чтения на основной движок и корректные флаги readonly.
  - [x] Проверен выброс `DatabaseConfigurationError` при некорректной схеме DSN реплики.
  - [x] Воспроизведён таймаут health-check для движка с контролируемым `DatabaseStartupError`.
- **Зависимости**: tests/database/test_db_router_fallbacks.py, docs/changelog.md

## Задача: Prediction worker error guards
- **Статус**: Завершена
- **Описание**: Зафиксировать негативные сценарии воркера предсказаний: ошибки ядра, таймауты Redis-lock и валидацию payload.
- **Шаги выполнения**:
  - [x] Смоделированы исключения ядра и проверена маскировка чувствительных данных в QueueError.
  - [x] Воспроизведён таймаут Redis-lock, подтверждена единичность постановки job и статус `lock_timeout`.
  - [x] Проверена обработка «грязного» payload (отрицательный `n_sims`) с предсказуемым исключением.
- **Зависимости**: tests/workers/test_prediction_worker_errors.py, docs/changelog.md

## Задача: Makefile coverage цели
- **Статус**: Завершена
- **Описание**: Синхронизировать автоматизацию покрытия: обновить цели Makefile и регенерацию отчётов.
- **Шаги выполнения**:
  - [x] Перенастроены `test-all` и `coverage-html` на общий запуск pytest и жёсткие пороги coverage enforcement.
  - [x] Зафиксирован экспорт `reports/coverage_summary.json` и топ-20 файлов через `--print-top`.
  - [x] Добавлена цель `reports-gaps` для вызова `python -m tools.coverage_gaps`.
- **Зависимости**: Makefile, tools/coverage_enforce.py, tools/coverage_gaps.py, docs/changelog.md

## Задача: Coverage gaps отчёт
- **Статус**: Завершена
- **Описание**: Автоматизировать построение Markdown-отчёта по пропущенным строкам покрытия с группировкой по ключевым пакетам.
- **Шаги выполнения**:
  - [x] Реализован парсер `coverage.xml` и определение пакетов workers/database/services/core/services.
  - [x] Сформирован Markdown-отчёт `reports/coverage_gaps.md` с ТОП-20 файлами и диапазонами пропущенных строк.
  - [x] Обновлены записи changelog/tasktracker для фиксации нового процесса.
- **Зависимости**: tools/coverage_gaps.py, reports/coverage_gaps.md, docs/changelog.md, docs/tasktracker.md

## Задача: Контроль покрытия CLI
- **Статус**: Завершена
- **Описание**: Добавить пороги CLI, экспорт JSON и вывод проблемных файлов в coverage_enforce.py.
- **Шаги выполнения**:
  - [x] Реализованы параметры `--total-min`, `--pkg-min` и `--print-top`.
  - [x] Добавлен экспорт summary в формате JSON с пакетами и файлами.
  - [x] Настроена проверка порогов с сообщением об ошибке и выходом с кодом 2.
- **Зависимости**: tools/coverage_enforce.py, docs/changelog.md

## Задача: E6.3 — Актуализация конфигурации coverage
- **Статус**: Завершена
- **Описание**: Уточнить анализируемые каталоги и исключаемые строки в `.coveragerc` для стабильных отчётов покрытия.
- **Шаги выполнения**:
  - [x] Добавлена опция `relative_files = True` и перечислены каталоги `telegram`, `workers`, `services`, `core`, `database`, `scripts`.
  - [x] Настроены правила `exclude_lines` и список `omit` для исключения служебных файлов.
  - [x] Обновлены записи в `docs/changelog.md` и `docs/tasktracker.md`.
- **Зависимости**: .coveragerc, docs/changelog.md, docs/tasktracker.md

## Задача: E6.2 — Coverage thresholds enforcement
- **Статус**: Завершена
- **Описание**: Сконфигурировать coverage.py, исключить не-кодовые файлы и ввести жёсткие пороги по проекту и критическим пакетам без изменения бизнес-логики.
- **Шаги выполнения**:
  - [x] Создан `.coveragerc` с исключениями миграций, документации, тестов, shell-скриптов и `__init__.py` без логики.
  - [x] Реализован `tools.coverage_enforce` для разбора `coverage.xml`, проверки порогов и выгрузки `reports/coverage_summary.json`.
  - [x] Обновлены цели `Makefile` и workflow `ci.yml`, запускающие enforcement до генерации HTML-отчёта.
  - [x] README, CHANGELOG и docs/changelog зафиксировали конфигурацию и требования.
- **Зависимости**: .coveragerc, tools/coverage_enforce.py, Makefile, .github/workflows/ci.yml, README.md, CHANGELOG.md, docs/changelog.md, docs/tasktracker.md

## Задача: E6 — Error handling coverage hardening
- **Статус**: Завершена
- **Описание**: Закрыть ветки ошибок Telegram-бота, очередей, DB router и prestart без изменения бизнес-логики.
- **Шаги выполнения**:
  - [x] Добавлены тесты `/predict` `/match` `/today` и форматирования виджетов для экранирования и сообщений.
  - [x] Покрыты очереди: маппинг статусов RQ, TTL/priority политики TaskManager, маскирование логов.
  - [x] Подготовлены тесты негативных сценариев DB Router, prestart и PredictorService (seed/NaN).
- **Зависимости**: tests/bot/test_handlers_errors.py, tests/telegram/test_widgets_escape.py, workers/queue_adapter.py, tests/workers/test_queue_adapter_errors.py, tests/workers/test_task_manager_policies.py, tests/database/test_db_router_errors.py, tests/scripts/test_prestart.py, tests/services/test_predictor_determinism.py, tests/security/test_masking.py, reports/coverage_gaps.md, docs/changelog.md

## Задача: E6 — CI покрытие и отчёты
- **Статус**: Завершена
- **Описание**: Включить жёсткие пороги coverage, добавить snapshot/RC отчёты и обновить CI с артефактами без изменения бизнес-логики.
- **Шаги выполнения**:
  - [x] Обновлены pytest-конфиги и Makefile (`test-fast`, `test-smoke`, `test-all`, `coverage-html`).
  - [x] Добавлены скрипты отчётов (`bot_e2e_snapshot.py`, `rc_summary.py`) и утилиты контроля покрытия.
  - [x] Переписан workflow `.github/workflows/ci.yml` с последовательными стадиями и публикацией артефактов.
  - [x] README, CHANGELOG, docs/changelog/tasktracker отражают новые процессы и пороги.
- **Зависимости**: pytest.ini, Makefile, scripts/coverage_utils.py, scripts/enforce_coverage.py, reports/bot_e2e_snapshot.py, reports/rc_summary.py, .github/workflows/ci.yml, README.md, CHANGELOG.md, docs/changelog.md, docs/tasktracker.md

## Задача: E5 — Production Docker/Entrypoint for Amvera
- **Статус**: В процессе
- **Описание**: Подготовить production Docker-образ с prestart-хуком (alembic + health-check) и обновить документацию под деплой на Amvera.
- **Шаги выполнения**:
  - [x] Добавить многоступенчатый Dockerfile и `.dockerignore`.
  - [x] Реализовать `scripts/entrypoint.sh` и `scripts/prestart.py` с проверками БД/Redis.
  - [x] Обновить Makefile/README/CHANGELOG/tasktracker под новый процесс деплоя.
  - [ ] Прогнать `docker build`/`docker run` в окружении Amvera.
- **Зависимости**: Dockerfile, .dockerignore, scripts/entrypoint.sh, scripts/prestart.py, Makefile, README.md, CHANGELOG.md, docs/changelog.md, docs/tasktracker.md, database/db_router.py, workers/redis_factory.py

## Задача: E4 — Recommendation engine invariants
- **Статус**: Завершена
- **Описание**: Нормализовать интерфейсы RecommendationEngine/PredictorService/воркера и гарантировать инварианты вероятностей.
- **Шаги выполнения**:
  - [x] Переписан `services/recommendation_engine` и добавлен фасад `core/services/predictor.py`.
  - [x] Обновлён `workers/prediction_worker.py` на DI с Redis-lock и статусами очереди.
  - [x] Добавлены тесты `tests/ml/test_prediction_invariants.py` и `tests/workers/test_prediction_worker.py`.
  - [x] README, Project.md и changelog отражают новые инварианты.
- **Зависимости**: services/recommendation_engine.py, core/services/predictor.py, workers/prediction_worker.py, tests/ml/test_prediction_invariants.py, tests/workers/test_prediction_worker.py, README.md, docs/Project.md, docs/changelog.md

## Задача: E3 — Telegram UX и форматирование
- **Статус**: Завершена
- **Описание**: Обновить команды Telegram-бота, привести обработчики к DI, добавить форматирование ответов и smoke-тесты.
- **Шаги выполнения**:
  - [x] Добавлены DI-зависимости и новый модуль `telegram/widgets.py`.
  - [x] Переписаны обработчики `/help`, `/model`, `/today`, `/match`, `/predict` и обновлена регистрация роутеров.
  - [x] Добавлены README раздел, changelog и тесты `tests/bot/*`.
- **Зависимости**: telegram/dependencies.py, telegram/services.py, telegram/widgets.py, telegram/handlers/*, tests/bot, README.md, docs/changelog.md

## Задача: E1 — DB Router и Alembic
- **Статус**: Завершена
- **Описание**: Реализовать асинхронный роутер баз данных с поддержкой SQLite/Postgres и подготовить Alembic.
- **Шаги выполнения**:
  - [x] Добавлен `database/db_router.py` с раздельными сессиями чтения/записи и health-check.
  - [x] Сконфигурировано async-окружение Alembic и ревизия `predictions`.
  - [x] Созданы тесты `tests/database/test_db_router.py` и обновлена конфигурация `Settings`.
- **Зависимости**: database/db_router.py, database/migrations, tests/database/test_db_router.py, config.py, docs/Project.md

## Задача: Amvera audit and planning
- **Статус**: Завершена
- **Описание**: Провести аудит состояния бота и подготовить план перехода на Amvera (PostgreSQL+Redis).
- **Шаги выполнения**:
  - [x] Проанализирован код и документация, сформирован отчёт `audit.md`.
  - [x] Сформирован план `refactor_plan.md` с этапами E1–E7.
  - [x] Обновлены changelog/tasktracker записями о проделанной работе.
- **Зависимости**: audit.md, refactor_plan.md, docs/changelog.md

## Задача: Redis cache hardening
- **Статус**: Завершена
- **Описание**: Устранить ошибки Redis-хелперов и покрыть кэш лайнапов тестами.
- **Шаги выполнения**:
  - [x] Синхронизирован `versioned_key` с настройками без `await` и добавлен docstring.
  - [x] Исправлены `set_with_ttl` и `invalidate_lineups` для корректного TTL и сериализации.
  - [x] Добавлены юнит-тесты `tests/database/test_cache_postgres.py` и прогнан полный `pytest`.
- **Зависимости**: database/cache_postgres.py, tests/database/test_cache_postgres.py, docs/changelog.md

## Задача: Integrator roadmap Part 1–3
- **Статус**: Завершена
- **Описание**: Закрыть дорожную карту интегратора по трём частям: numeric контроль, отчёты и покрытия.
- **Шаги выполнения**:
  - [x] Part 1 — зафиксирован staged CI с numeric enforcement и офлайн зависимостями.
  - [x] Part 2 — расширены отчёты и CLI retrain, обновлены итоговые документы.
  - [x] Part 3 — добавлены coverage-артефакты, «бережный» lint и финальные отчёты.
- **Зависимости**: .github/workflows/ci.yml, README.md, reports/RUN_SUMMARY.md, docs/changelog.md

## Задача: CLI retrain orchestration
- **Статус**: Завершена
- **Описание**: Добавить CLI `scripts/cli.py` с переобучением, расписанием и статусом, обновить документацию и тесты.
- **Шаги выполнения**:
  - [x] Реализована команда `retrain run` с обновлением LocalModelRegistry и отчётов.
  - [x] Добавлены подкоманды `schedule`/`status` и smoke-тест CLI.
  - [x] Обновлены README, ARCHITECTURE, changelog, RUN_SUMMARY и tasktracker.
- **Зависимости**: scripts/cli.py, tests/smoke/test_cli_retrain.py, README.md, ARCHITECTURE.md, docs/changelog.md, reports/RUN_SUMMARY.md

## Задача: Перенос data_processor в пакет
- **Статус**: Завершена
- **Описание**: Вынести в пакет app/data_processor валидацию, построение признаков и матрицу признаков с покрытиями ≥80%.
- **Шаги выполнения**:
  - [x] Подготовлены матчевые признаки и rolling агрегаты без утечек.
  - [x] Сформированы матрицы признаков с log1p-таргетом и поддержкой tuple.
  - [x] Написаны модульные тесты и обновлены отчёты/документация.
- **Зависимости**: app/data_processor, tests/data_processor, docs/changelog.md, reports/RUN_SUMMARY.md

## Задача: Data processor scaffolding
- **Статус**: Завершена
- **Описание**: Подготовить каркас пакета `app/data_processor` без миграции существующей логики.
- **Шаги выполнения**:
  - [x] Созданы модули validate/features/matrix с заглушками и аннотациями.
  - [x] Обновлён `__init__.py` с версией пакета и экспортами.
  - [x] Добавлены тесты на отказ при пустом `DataFrame`.
- **Зависимости**: app/data_processor, tests/data_processor

## Задача: Монте-Карло и Bi-Poisson
- **Статус**: Завершена
- **Описание**: Добавить расчёт энтропии рынков и параметры симуляции.
- **Шаги выполнения**:
  - [x] Реализован модуль энтропии и тесты.
  - [x] Добавлены переменные окружения и настройки.
  - [x] Интеграция в prediction_pipeline и отчёты.
- **Зависимости**: services/simulator.py, ml/metrics/entropy.py, config.py, app/config.py, .env.example, ml/sim/bivariate_poisson.py

## Задача: Ruff warnings cleanup
- **Статус**: Завершена
- **Описание**: Устранить предупреждения Ruff F401/I001/UP037/UP035/UP045.
- **Шаги выполнения**:
  - [x] Удалены неиспользуемые импорты и упорядочены импорты.
  - [x] Обновлены аннотации типов на современный синтаксис.
  - [x] Прогнаны pre-commit, линты и тесты.
- **Зависимости**: scripts/syntax_partition.py, tests/test_ml.py, services/prediction_pipeline.py, workers/retrain_scheduler.py, docs/changelog.md, docs/tasktracker.md, reports/RUN_SUMMARY.md

## Задача: Fix Ruff leftovers and verbose smoke
- **Статус**: Завершена
- **Описание**: Устранить предупреждения Ruff B904/C401/ERA001 и сделать цель smoke говорящей.
- **Шаги выполнения**:
  - [x] Исправлены предупреждения Ruff B904, C401 и ERA001.
  - [x] Обновлена цель Makefile `smoke`, добавлена проверка `jobs_registered_total`.
  - [x] Прогнаны pre-commit, линт и тесты.
- **Зависимости**: app/config.py, config.py, scripts/ruff_partition.py, scripts/run_training_pipeline.py, telegram/utils/formatter.py, tests/smoke/test_endpoints.py, Makefile, docs/changelog.md, docs/tasktracker.md, reports/RUN_SUMMARY.md

## Задача: SportMonks stub default and Ruff cleanup
- **Статус**: Завершена
- **Описание**: Включить STUB SportMonks при отсутствии ключа и устранить указанные предупреждения Ruff.
- **Шаги выполнения**:
  - [x] Автовключение STUB в tests/conftest.py.
  - [x] Исправлены предупреждения Ruff (B904, B025, ERA001, UP038, C401) и синтаксис telegram/models.py.
  - [x] Прогнаны pre-commit, линт и тесты.
- **Зависимости**: tests/conftest.py, services/recommendation_engine.py, telegram/bot.py, ml/models/poisson_regression_model.py, services/sportmonks_client.py, ml/modifiers_model.py, scripts/black_partition.py, telegram/models.py, docs/changelog.md, docs/tasktracker.md

## Задача: Fix offline pre-commit configuration
- **Статус**: Завершена
- **Описание**: Обновить офлайн pre-commit конфиг, добавить локальные хуки и задокументировать изменения.
- **Шаги выполнения**:
  - [x] Исправлен `.pre-commit-config.offline.yaml` (ruff check, локальные хуки, isort/black).
  - [x] Обновлена цель `pre-commit-offline` в `Makefile`.
  - [x] Обновлены README, changelog и tasktracker.
  - [x] Прогнаны линтеры, тесты и smoke.
- **Зависимости**: .pre-commit-config.offline.yaml, Makefile, README.md, docs/changelog.md, docs/tasktracker.md

## Задача: Offline numeric stack support
- **Статус**: Завершена
- **Описание**: Настроить кеш колёс, расширить офлайн pre-commit ruff и задокументировать CI numeric enforcement.
- **Шаги выполнения**:
  - [x] Обновлён pip.conf с find-links и создан каталог wheels
  - [x] Добавлен ruff в .pre-commit-config.offline.yaml
  - [x] В README добавлен раздел CI numeric enforcement
  - [x] Обновлены docs/changelog.md и docs/tasktracker.md
- **Зависимости**: pip.conf, wheels/README.md, .pre-commit-config.offline.yaml, README.md, docs/changelog.md, docs/tasktracker.md

## Задача: Numpy guard and CI fallback
- **Статус**: Завершена
- **Описание**: Добавить пропуск numpy/pandas тестов без стека, обновить CI и документацию.
- **Шаги выполнения**:
  - [x] Добавлен tests/conftest_np_guard.py
  - [x] Обновлены pytest.ini, README и CI workflow
  - [x] Прогнаны линтеры и тесты
- **Зависимости**: tests/conftest_np_guard.py, pytest.ini, README.md, .github/workflows/ci.yml, docs/changelog.md, docs/tasktracker.md

## Задача: Pin numpy/pandas and update ML docs
- **Статус**: Завершена
- **Описание**: Добавить ограничения numpy>=1.26,<2.0 и pandas==2.2.2, пересобрать окружение, проверить numpy.math, обновить ML-стек и прогнать pytest.
- **Шаги выполнения**:
  - [x] Обновлены requirements и constraints
  - [x] make deps-fix
  - [x] Поиск numpy.math
  - [x] Запущен pytest
  - [x] Обновлены README и ARCHITECTURE
- **Зависимости**: requirements.txt, constraints.txt, README.md, ARCHITECTURE.md, docs/changelog.md, docs/tasktracker.md

## Задача: Cleanup TODOs and CI smoke
- **Статус**: Завершена
- **Описание**: Удалить устаревшие TODO, сократить предупреждения Ruff, добавить smoke/e2e в CI и обновить документацию.
- **Шаги выполнения**:
  - [x] Убраны TODO в handlers и train_model
  - [x] scripts/train_model.py читает `SEASON_ID`
  - [x] CI запускает smoke и e2e тесты
  - [x] README и ARCHITECTURE дополнены
- **Зависимости**: app/handlers.py, telegram/handlers/start.py, telegram/handlers/help.py, scripts/train_model.py, .github/workflows/ci.yml, README.md, ARCHITECTURE.md, .env.example

## Задача: Offline pre-commit and ML tests
- **Статус**: Завершена
- **Описание**: Починить offline pre-commit config и добавить контрактные/ML тесты.
- **Шаги выполнения**:
  - [x] Исправлен `.pre-commit-config.offline.yaml`
  - [x] Добавлен тест ENV-контракта
  - [x] Написан e2e-тест PredictionPipeline + LocalModelRegistry
  - [x] Добавлен smoke-тест TaskManager.cleanup
  - [x] Обновлены README и ARCHITECTURE.md
- **Зависимости**: .pre-commit-config.offline.yaml, tests/contracts/test_env_example_contract.py, tests/test_prediction_pipeline_local_registry_e2e.py, tests/smoke/test_task_manager_cleanup.py, README.md, ARCHITECTURE.md

## Задача: ENV contract sync
- **Статус**: Завершена
- **Описание**: Синхронизировать .env.example и app/config.py с обязательными переменными.
- **Шаги выполнения**:
  - [x] Обновлены .env.example и app/config.py
  - [x] Добавлены переменные ENV, PROMETHEUS__*, RETRAIN_CRON
  - [x] Прогнаны тесты
- **Зависимости**: .env.example, app/config.py

## Задача: Replace legacy headers with docstrings
- **Статус**: Завершена
- **Описание**: Конвертировать C-style заголовки в telegram/middlewares и ml/* на docstrings.
- **Шаги выполнения**:
  - [x] Обновлены соответствующие файлы
  - [x] Прогнаны линтеры
- **Зависимости**: telegram/middlewares.py, ml/

## Задача: Local model registry and task cleanup
- **Статус**: Завершена
- **Описание**: Добавить LocalModelRegistry и функции очистки задач.
- **Шаги выполнения**:
  - [x] Реализован LocalModelRegistry и сохранение модели
  - [x] Добавлены TaskManager.clear_all и cleanup с тестами
  - [x] Обновлены PredictionPipeline и train_base_glm
- **Зависимости**: app/ml/model_registry.py, app/ml/train_base_glm.py, app/ml/prediction_pipeline.py, workers/task_manager.py, tests/test_registry_local.py, tests/test_task_manager_cleanup.py

## Задача: SportMonks stub client
- **Статус**: Завершена
- **Описание**: Добавить клиента SportMonks с режимом заглушки и тесты.
- **Шаги выполнения**:
  - [x] Реализовать клиента с режимом заглушки
  - [x] Автоматически включать stub в тестах
  - [x] Добавить юнит-тесты и обновить .env.example
- **Зависимости**: app/integrations/sportmonks_client.py, tests/test_sportmonks_stub.py, .env.example

## Задача: Add endpoint smoke tests and offline lint in CI
- **Статус**: Завершена
- **Описание**: Добавить smoke-тесты /health, /metrics, /__smoke__/retrain, /__smoke__/sentry и обновить CI для использования make pre-commit-smart.
- **Шаги выполнения**:
  - [x] Добавить tests/smoke/test_endpoints.py
  - [x] Обновить .github/workflows/ci.yml
  - [x] Прогнать lint и тесты
- **Зависимости**: tests/smoke/test_endpoints.py, .github/workflows/ci.yml

## Задача: Unify observability and add metrics test
- **Статус**: Завершена
- **Описание**: Удалить дублирующий observability, обновить эндпоинт /metrics и добавить smoke-тест.
- **Шаги выполнения**:
  - [x] Удалить устаревший observability.py
  - [x] Обновить endpoint /metrics
  - [x] Добавить smoke-тест
- **Зависимости**: app/observability.py, tests/smoke/test_metrics_endpoint.py

## Задача: Replace C-style headers with docstrings
- **Статус**: Завершена
- **Описание**: Переписать заголовки файлов app/data_processor на docstring.
- **Шаги выполнения**:
  - [x] Конвертировать заголовки в docstring
  - [x] Прогнать lint и pytest
- **Зависимости**: app/data_processor/*

## Задача: Align env example with config
- **Статус**: Завершена
- **Описание**: Синхронизировать .env.example с app/config.py и добавить алиасы для настроек.
- **Шаги выполнения**:
  - [x] Добавить недостающие переменные окружения
  - [x] Добавить алиасы для Prometheus и RateLimit
  - [x] Прогнать lint и pytest
- **Зависимости**: .env.example, app/config.py

## Задача: Repository inventory refresh
- **Статус**: Завершена
- **Описание**: Обновить снимки документации, структуры и конфигураций.
- **Шаги выполнения**:
  - [x] Список документации
  - [x] Дерево каталогов и модули
  - [x] TODO/FIXME/HACK/WIP/XXX
  - [x] Конфиги и инструменты
- **Зависимости**: reports/INVENTORY.md

## Задача: Repository inventory report
- **Статус**: Завершена
- **Описание**: Собрать документацию, структуру каталогов и конфигурации репозитория.
- **Шаги выполнения**:
  - [x] Список документации
  - [x] Дерево каталогов и модули
  - [x] TODO/FIXME/HACK/WIP/XXX
  - [x] Конфиги и инструменты
- **Зависимости**: reports/INVENTORY.md

## Задача: Smart pre-commit fallback
- **Статус**: Завершена
- **Описание**: Добавить скрипт офлайн-запуска pre-commit и цель Makefile.
- **Шаги выполнения**:
  - [x] Добавить scripts/run_precommit.py
  - [x] Создать .pre-commit-config.offline.yaml и цель pre-commit-smart
  - [x] Обновить README и документацию
  - [x] Описать кеш `PRE_COMMIT_HOME`
- **Зависимости**: scripts/run_precommit.py, .pre-commit-config.offline.yaml, Makefile, README.md

## Задача: Feature-flag retrain scheduler
- **Статус**: Завершена
- **Описание**: Включить планировщик переобучения по фиче-флагу и добавить smoke эндпоинт.
- **Шаги выполнения**:
  - [x] Реализовать in-memory runtime scheduler
  - [x] Провести wiring в app.main и добавить smoke эндпоинт
  - [x] Обновить README и .env.example
- **Зависимости**: workers/runtime_scheduler.py, app/main.py, README.md, .env.example, tests/smoke/test_retrain_registration.py

## Задача: Скелеты сервисов и планировщика
- **Статус**: Завершена
- **Описание**: Добавить минимальные скелеты PredictionPipeline и Retrain Scheduler, тесты и обновить документацию.
- **Шаги выполнения**:
  - [x] Реализовать `services/prediction_pipeline.py`
  - [x] Реализовать `workers/retrain_scheduler.py`
  - [x] Добавить тесты и обновить README/.env
- **Зависимости**: services/prediction_pipeline.py, workers/retrain_scheduler.py, tests/test_services_workers_minimal.py, README.md, .env.example
## Задача: Синхронизация pandas
- **Статус**: Завершена
- **Описание**: Закрепить версию `pandas==2.2.2` в зависимостях проекта.
- **Шаги выполнения**:
  - [x] Обновить `requirements.txt`
  - [x] Проверить `constraints.txt`
- **Зависимости**: requirements.txt, constraints.txt

## Задача: Завершить record_prediction
- **Статус**: Завершена
- **Описание**: Реализовать запись прогнозов и обновление скользящих метрик ECE и LogLoss.
- **Шаги выполнения**:
  - [x] Дописать `record_prediction`
  - [x] Добавить алёрт Sentry при ECE>0.05
- **Зависимости**: metrics/metrics.py, tests/test_metrics.py

## Задача: Проектный аудит и план доводки
- **Статус**: Завершена
- **Описание**: Провести аудит проекта и подготовить план доводки до продакшна.
- **Шаги выполнения**:
  - [x] Собрать инвентаризацию и источники
  - [x] Сопоставить документацию с кодом
  - [x] Выявить незавершённости и риски
  - [x] Сформировать отчёты PROJECT_AUDIT.md и ACTION_PLAN.md
- **Зависимости**: reports/PROJECT_AUDIT.md, reports/ACTION_PLAN.md

## Задача: Детектор синтаксических ошибок и выборочный lint
- **Статус**: Завершена
- **Описание**: Автоматически исключать непарсящие файлы и линтить только корректные.
- **Шаги выполнения**:
  - [x] Создать скрипт `scripts/syntax_partition.py`
  - [x] Обновить цель `lint-app` в Makefile
  - [x] Прогнать setup, линты, тесты и smoke
- **Зависимости**: scripts/syntax_partition.py, Makefile, .env.blackexclude, .ruffignore

## Задача: Адресное игнорирование Ruff и lint-app
- **Статус**: Завершена
- **Описание**: Утихомирить предупреждения в __init__.py и тестах; добавить lint-app.
- **Шаги выполнения**:
  - [x] Обновить per-file-ignores в ruff.toml
  - [x] Добавить цель lint-app в Makefile
  - [x] Прогнать автофиксы и проверки
- **Зависимости**: ruff.toml, Makefile, app

## Задача: Глобальная проверка NumPy/Pandas и маркировка тестов
- **Статус**: Завершена
- **Описание**: Добавить проверку стека NumPy/Pandas и пометить тесты маркером needs_np.
- **Шаги выполнения**:
  - [x] Добавить проверку стека NumPy/Pandas и авто-скип тестов
  - [x] Пометить тесты маркером `needs_np`
  - [x] Прогнать lint, тесты и smoke
- **Зависимости**: tests/conftest.py, tests/integration/test_end_to_end.py, tests/test_ml.py, tests/test_metrics.py, tests/test_pipeline_stub.py, tests/test_services.py, tests/test_settings.py

## Задача: Стабилизация CI при отсутствии numpy/pandas
- **Статус**: Завершена
- **Описание**: Параметризовать lint и автоматически пропускать тесты при недоступных numpy/pandas.
- **Шаги выполнения**:
  - [x] Параметризовать цель lint в Makefile
  - [x] Добавить `pytest.importorskip` в тесты
  - [x] Создать локальный `pip.conf`
- **Зависимости**: Makefile, tests/integration/test_end_to_end.py, tests/test_metrics.py, tests/test_ml.py, pip.conf

## Задача: Пины численного стека и Ruff игнор
- **Статус**: Завершена
- **Описание**: Добавить constraints.txt, обновить Makefile и настроить адресное игнорирование Ruff.
- **Шаги выполнения**:
  - [x] Создать constraints.txt
  - [x] Заменить цель setup и добавить deps-fix в Makefile
  - [x] Добавить `.ruffignore` и `scripts/ruff_partition.py`
- **Зависимости**: constraints.txt, Makefile, .ruffignore, scripts/ruff_partition.py

## Задача: Финализация Black и снижение шума Ruff
- **Статус**: Завершена
- **Описание**: Добавить force-exclude для Black и ограничить Ruff каталогами app/tests.
- **Шаги выполнения**:
  - [x] Ввести переменные BLACK_EXCLUDE/BLACK_EXTRA и подключить .env.blackexclude
  - [x] Переписать scripts/black_partition.py
  - [x] Ограничить Ruff проверкой app и tests
  - [x] Добавить фикстуру _defaults_env в tests/conftest.py
- **Зависимости**: Makefile, scripts/black_partition.py, tests/conftest.py, .gitignore, .env.blackexclude

## Задача: Стабилизация Black и Ruff
- **Статус**: Завершена
- **Описание**: Снизить шум линтера и обеспечить алиасы настроек.
- **Шаги выполнения**:
  - [x] Обновить конфигурацию Black и скрипт black_partition.py
  - [x] Переписать ruff.toml с per-file ignores
  - [x] Добавить алиасы APP_NAME и DEBUG в Settings
  - [x] Гарантировать включение метрик в тестах
  - [x] Обновить зависимости и прогнать линтеры и тесты
- **Зависимости**: pyproject.toml, scripts/black_partition.py, ruff.toml, app/config.py, tests/conftest.py, requirements.txt

## Задача: Стабилизация setup и автоформатирования
- **Статус**: Завершена
- **Описание**: Добавить fallback установки тулов и автоматизацию Black.
- **Шаги выполнения**:
  - [x] Добавить proxy-safe fallback в Makefile
  - [x] Добавить конфиг Black и скрипт black_partition.py
- **Зависимости**: Makefile, pyproject.toml, scripts/black_partition.py

## Задача: Стабилизация CI: импорт и конфиги
- **Статус**: Завершена
- **Описание**: Починить импорт пакета app, развести конфиги Ruff и Isort, нормализовать заголовки и зафиксировать версии тулов.
- **Шаги выполнения**:
  - [x] Починить импорт пакета app
  - [x] Развести конфиги Ruff и Isort
  - [x] Нормализовать заголовки файлов
  - [x] Зафиксировать версии тулов
- **Зависимости**: tests/conftest.py, ruff.toml, .isort.cfg, scripts/fix_headers.py, Makefile

## Задача: Стабилизация CI и настроек
- **Статус**: Завершена
- **Описание**: Сброс кэша настроек, включение метрик и снижение шума линтера.
- **Шаги выполнения**:
  - [x] Обновлён `ruff.toml` и цель `lint`
  - [x] Добавлены `reset_settings_cache` и фикстура `_force_prometheus_enabled`
  - [x] Прогнаны `make lint` и `make test`
- **Зависимости**: ruff.toml, Makefile, app/config.py, tests/conftest.py

## Задача: Базовая инфраструктура и тесты
- **Статус**: Завершена
- **Описание**: Добавить README, конфиги инструментов и базовые тесты.
- **Шаги выполнения**:
  - [x] Создан README и ARCHITECTURE
  - [x] Добавлены конфиги .env.example, pytest, mypy, ruff, Makefile
  - [x] Реализован smoke-скрипт и интеграционные тесты
- **Зависимости**: README.md, ARCHITECTURE.md, scripts/verify.py, tests

## Задача: Контроль метрик и Sentry smoke-тест
- **Статус**: Завершена
- **Описание**: Добавить эндпоинт /__smoke__/sentry и тест проверки /metrics.
- **Шаги выполнения**:
  - [x] Добавлен эндпоинт /__smoke__/sentry
  - [x] Написан тест на health и /metrics
- **Зависимости**: app/main.py, tests/test_metrics_sentry.py

## Задача: Очистка TODO в CLI и handlers
- **Статус**: Завершена
- **Описание**: Заменить TODO на явные предупреждения и добавить тест.
- **Шаги выполнения**:
  - [x] Реализована явная заглушка в CLI 'retrain'
  - [x] some_handler возвращает note о незавершённых правилах
  - [x] Добавлен тест на наличие note
- **Зависимости**: app/cli.py, app/handlers.py, tests/test_todo_barriers.py

## Задача: Заглушки ML-пайплайна
- **Статус**: Завершена
- **Описание**: Добавить PredictionPipeline, заглушки обучения и планировщик переобучения.
- **Шаги выполнения**:
  - [x] Реализован PredictionPipeline
  - [x] Заглушки обучения и переобучения
  - [x] Добавлен тест пайплайна
- **Зависимости**: app/ml, tests

## Задача: Починка pre-commit и CI
- **Статус**: Завершена
- **Описание**: Пин ревизий pre-commit хуков и обновление workflow CI с кэшем pip.
- **Шаги выполнения**:
  - [x] Обновлены ревизии и добавлены isort и базовые хуки
  - [x] Настроен workflow с матрицей Python и кэшем pip
  - [x] Прогон pre-commit и pytest
- **Зависимости**: .pre-commit-config.yaml, .github/workflows/ci.yml

## Задача: Миграция конфигов на Pydantic v2
- **Статус**: Завершена
- **Описание**: Перевести конфигурацию на pydantic v2 и настроить pydantic-settings.
- **Шаги выполнения**:
  - [x] Обновлены зависимости и pyproject.toml
  - [x] Реализован пакет app с настройками и наблюдаемостью
  - [x] Добавлены тесты настроек
- **Зависимости**: —

## Задача: Наблюдаемость Sentry и Prometheus
- **Статус**: Завершена
- **Описание**: Подключить Sentry, экспорт Prometheus и метрики ECE/LogLoss с алёртом.
- **Шаги выполнения**:
  - [x] Добавлены зависимости и настройки
  - [x] Реализован модуль метрик и HTTP-сервер
  - [x] Интеграция с Sentry и оповещение при ECE>0.05
- **Зависимости**: Project.md (разделы 3,6)

## Задача: Валидация команд и rate-limit
- **Статус**: Завершена
- **Описание**: Добавить Pydantic-модели команд, валидацию обработчиков и middleware rate-limit.
- **Шаги выполнения**:
  - [x] Созданы Pydantic-модели команд
  - [x] Добавлена валидация в обработчики
  - [x] Реализовано и подключено middleware rate-limit
- **Зависимости**: Project.md (разделы 3,7)

## Задача: Настройка тестов и CI
- **Статус**: Завершена
- **Описание**: Добавить юнит-тесты для services и ml, настроить pre-commit и GitHub Actions.
- **Шаги выполнения**:
  - [x] Добавлены unit-тесты для services и ml
  - [x] Настроен pre-commit с Black, Ruff и mypy
  - [x] Добавлен workflow для линтеров и pytest
- **Зависимости**: —

## Задача: Очистка конфликтов и обновление зависимостей
- **Статус**: Завершена
- **Описание**: Удалить конфликтные маркеры, свести зависимости и пересобрать окружение.
- **Шаги выполнения**:
  - [x] Удалены маркеры конфликтов в main.py и requirements.txt
  - [x] Сведены зависимости в requirements.txt без повторов
  - [x] Пересобрано окружение офлайн и закреплены версии линтеров
- **Зависимости**: —

## Задача: Базовые λ (Poisson-GLM) с валидацией
- **Статус**: Завершена
- **Описание**: Обучить GLM по xG/xGA с recency-весами и L2, зафиксировать λ_base и экспортировать model_info.json.
- **Шаги выполнения**:
  - [x] Подготовить датасет
  - [x] Обучить и зафиксировать артефакты
  - [x] Добавить unit-тесты на инварианты
- **Зависимости**: Project.md (раздел 4.1)

## Задача: Динамические модификаторы (обучаемый мультипликатор)
- **Статус**: Завершена
- **Описание**: Реализовать f(context) c оффсетом log(λ_base), каппинг 0.7–1.4, логирование факторов.
- **Шаги выполнения**:
  - [x] Сформировать контекстные фичи
  - [x] Обучить модель и провести калибровку
  - [x] Интегрировать в prediction_pipeline
- **Зависимости**: GLM (λ_base)

## Задача: Монте-Карло и Bi-Poisson
- **Статус**: Завершена
- **Описание**: Реализовать симуляции ≥10k, рынки 1X2/Totals/BTTS/точные счёта, экспорт вероятностей.
- **Шаги выполнения**:
  - [x] Реализовать симулятор и корреляцию
  - [x] Добавить калибровку и отчёт по ECE
  - [x] Записать прогнозы в БД
- **Зависимости**: λ_final

## Задача: Рефакторинг ML-слоёв
- **Статус**: Завершена
- **Описание**: Вынести базовые λ, модификаторы, калибровку и симулятор в ml/*.
- **Шаги выполнения**:
  - [x] Создать base_poisson_glm, modifiers_model, calibration, montecarlo_simulator
  - [x] Обновить импорты в services, scripts и telegram
- **Зависимости**: Project.md (разделы 3-4)

## Задача: Логирование времени и Redis-lock
- **Статус**: Завершена
- **Описание**: Добавить middleware для измерения времени обработки и Redis-lock при генерации прогнозов.
- **Шаги выполнения**:
  - [x] Реализовано middleware замера времени и логирования p95/avg
  - [x] Подключено middleware в Dispatcher
  - [x] Добавлен Redis-lock в prediction_worker
- **Зависимости**: —

## Задача: Документирование лиг и валидация колонок
- **Статус**: Завершена
- **Описание**: Добавить список лиг и глубину ретро, описать ожидаемые колонки и их проверки, уточнить вопросы по данным.
- **Шаги выполнения**:
  - [x] Дополнен Project.md лигами и глубиной исторических данных
  - [x] Добавлены проверки обязательных колонок в data_processor.py
  - [x] Обновлён qa.md с уточнёнными вопросами по данным
- **Зависимости**: Project.md (раздел 5), services/data_processor.py

## Задача: Декомпозиция data_processor в пакет
- **Статус**: Завершена
- **Описание**: Создать пакет app/data_processor с фасадом и модулями validators, feature_engineering, transformers и io.
- **Шаги выполнения**:
  - [x] Создан пакет и фасад __init__.py
  - [x] Вынесены модули validators, feature_engineering, transformers и io
  - [x] Обновлена документация
- **Зависимости**: app/data_processor

## Задача: Документация и чек-листы
- **Статус**: Завершена
- **Описание**: Добавить AUDIT_REPORT.md и DEBT_CHECKLIST.md.
- **Шаги выполнения**:
  - [x] Добавлен AUDIT_REPORT.md
  - [x] Добавлен DEBT_CHECKLIST.md
- **Зависимости**: AUDIT_REPORT.md, DEBT_CHECKLIST.md

## Задача: Включить численные тесты
- **Статус**: Завершена
- **Описание**: Обеспечить запуск и контроль тестов, требующих NumPy/Pandas.
- **Шаги выполнения**:
  - [x] Удалена переменная NEEDS_NP_PATTERNS из CI
  - [x] Упрощён пропуск тестов через маркер `needs_np`
  - [x] Добавлена проверка отсутствия SKIP для численных тестов
- **Зависимости**: .github/workflows/ci.yml, tests/conftest_np_guard.py

## Задача: CI staged workflow
- **Статус**: Завершена
- **Описание**: Разделить GitHub Actions на стадии lint → unit → e2e/smoke → numeric с локальными wheels.
- **Шаги выполнения**:
  - [x] Перестроен workflow на отдельные jobs
  - [x] Добавлен fallback ruff/isort/black при недоступности pre-commit
  - [x] Стадия numeric использует `pip.conf` и проверяет отсутствие SKIP у @needs_np
- **Зависимости**: .github/workflows/ci.yml, docs/changelog.md, docs/tasktracker.md

## Задача: Sentry фичефлаг и метки метрик
- **Статус**: Завершена
- **Описание**: Добавить SENTRY_ENABLED, GIT_SHA, метки service/env/version и счётчик jobs_registered_total.
- **Шаги выполнения**:
  - [x] Добавлен SENTRY_ENABLED и GIT_SHA в .env.example и настройки.
  - [x] Реализован фичефлаг Sentry и метки в /metrics.
  - [x] Добавлен jobs_registered_total и обновлён /__smoke__/retrain.
- **Зависимости**: app/observability.py, app/config.py, workers/runtime_scheduler.py, app/main.py

## Задача: Валидация модификаторов
- **Статус**: Завершена
- **Описание**: Добавить метрики модификатора base vs final, CLI и CI-гейт.
- **Шаги выполнения**:
  - [x] Расчёт и логирование `glm_base_*` и `glm_mod_final_*`.
  - [x] CLI `scripts/validate_modifiers.py` с отчётом.
  - [x] CI-шаг проверки улучшения.
  - [x] Обновлена документация и сводки.
- **Зависимости**: services/prediction_pipeline.py, scripts/validate_modifiers.py, .github/workflows/ci.yml, README.md, ARCHITECTURE.md, docs/Project.md, tests/ml/test_modifiers_metrics.py, tests/smoke/test_validate_modifiers_cli.py

## Задача: Release Candidate v1.0.0-rc1
- **Статус**: Завершена
- **Описание**: Подготовить релиз-кандидат, зафиксировать версии и обновить CI.
- **Шаги выполнения**:
  - [x] Зафиксированы зависимости в requirements.lock
  - [x] Добавлен APP_VERSION и прокинут в метрики и отчёты
  - [x] Обновлён CI и шаг публикации RC summary
  - [x] Сформированы release notes
- **Зависимости**: app/config.py, metrics/metrics.py, scripts/run_simulation.py, requirements.lock, .github/workflows/ci.yml, reports/RELEASE_NOTES_RC.md

## Задача: Diagnostics v2 quality gates
- **Статус**: Завершена
- **Описание**: Расширить диагностику (data quality, drift, golden, calibration, bench) и включить CI-гейты.
- **Шаги выполнения**:
  - [x] Реализован пакет `app/data_quality` и интеграция в `tools/run_diagnostics.py`.
  - [x] Добавлены скрипты `tools/golden_regression.py`, `tools/drift_report.py`, `tools/bench.py` и пакет `app/diagnostics`.
  - [x] Обновлены отчёты, документация (`docs/quality_gates.md`, `docs/diagnostics.md`) и README-бейдж.
  - [x] Расширены тесты (`tests/diagnostics/*`), обновлён CI workflow и .env.example.
- **Зависимости**: tools/run_diagnostics.py, app/data_quality, app/diagnostics, tools/golden_regression.py, tools/drift_report.py, tools/bench.py, docs/quality_gates.md, docs/diagnostics.md, .github/workflows/ci.yml, README.md, .env.example, tests/diagnostics

## Задача: Унификация Makefile lint/test
- **Статус**: Завершена
- **Описание**: Привести цели `lint`, `fmt`, `test`, `check` в соответствие с требованиями CI и устранить ошибки `make`.
- **Шаги выполнения**:
  - [x] Настроены команды `lint`, `fmt`, `test` для использования стандартных инструментов (`ruff`, `black`, `isort`, `pytest`).
  - [x] Добавлена цель `check`, вызывающая линтеры и тесты последовательно.
  - [x] Объявлены `.PHONY`-цели и нормализованы табуляции в рецептах.
- **Зависимости**: Makefile, docs/changelog.md, docs/tasktracker.md
