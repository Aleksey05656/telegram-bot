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
