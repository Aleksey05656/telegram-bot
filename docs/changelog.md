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
