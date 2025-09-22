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
