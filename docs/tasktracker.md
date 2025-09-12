## Задача: Офлайн pre-commit
- **Статус**: Завершена
- **Описание**: Настроить локальный конфиг pre-commit и скрипты для офлайн-запуска.
- **Шаги выполнения**:
  - [x] Добавить `.pre-commit-config.offline.yaml`
  - [x] Реализовать `scripts/hooks/trailing_ws.py` и `scripts/hooks/eof_fixer.py`
  - [x] Обновить Makefile и README
- **Зависимости**: .pre-commit-config.offline.yaml, scripts/hooks/trailing_ws.py, scripts/hooks/eof_fixer.py, Makefile, README.md
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
