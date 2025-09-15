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
- **Статус**: В процессе
- **Описание**: Удалить конфликтные маркеры, свести зависимости и пересобрать окружение.
- **Шаги выполнения**:
  - [x] Удалены маркеры конфликтов в main.py и requirements.txt
  - [x] Сведены зависимости в requirements.txt без повторов
  - [ ] Пересобрать окружение
- **Зависимости**: —

## Задача: Базовые λ (Poisson-GLM) с валидацией
- **Статус**: В процессе
- **Описание**: Обучить GLM по xG/xGA с recency-весами и L2, зафиксировать λ_base и экспортировать model_info.json.
- **Шаги выполнения**:
  - [x] Подготовить датасет
  - [ ] Обучить и зафиксировать артефакты
  - [ ] Добавить unit-тесты на инварианты
- **Зависимости**: Project.md (раздел 4.1)

## Задача: Динамические модификаторы (обучаемый мультипликатор)
- **Статус**: Не начата
- **Описание**: Реализовать f(context) c оффсетом log(λ_base), каппинг 0.7–1.4, логирование факторов.
- **Шаги выполнения**:
  - [ ] Сформировать контекстные фичи
  - [ ] Обучить модель и провести калибровку
  - [ ] Интегрировать в prediction_pipeline
- **Зависимости**: GLM (λ_base)

## Задача: Монте-Карло и Bi-Poisson
- **Статус**: Не начата
- **Описание**: Реализовать симуляции ≥10k, рынки 1X2/Totals/BTTS/точные счёта, экспорт вероятностей.
- **Шаги выполнения**:
  - [ ] Реализовать симулятор и корреляцию
  - [ ] Добавить калибровку и отчёт по ECE
  - [ ] Записать прогнозы в БД
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
