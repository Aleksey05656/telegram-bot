# Coverage gaps

## Before (pytest --cov=./ --cov-report=term-missing)

- `scripts/prestart.py`: lines 8-100 — error flows and health checks not executed.
- `telegram/handlers/predict.py`: lines 34, 41, 49, 52-53, 57, 62-72 — validation branches and HTML escaping.
- `telegram/handlers/match.py`: lines 25-49 — missing “match not found” handling.
- `telegram/handlers/today.py`: lines 26, 31-42 — empty schedule messaging.
- `telegram/widgets.py`: lines 18-28, 33, 44, 58, 122, 126, 133, 137-138, 143, 152 — HTML escape and formatting edge cases.
- `telegram/services.py`: lines 27-189 — error paths across fixtures and predictions.
- `telegram/dependencies.py`: lines 69-116 — DI container fallbacks and validation.
- `telegram/bot.py`: lines 3-268 — bot setup and dependency wiring remain untested.
- `workers/task_manager.py`: lines 29-513 — TTL/priority policies and enqueue validations uncovered.
- `workers/queue_adapter.py`: rare RQ status mapping and exception handling not exercised.
- `workers/prediction_worker.py`: lines 56, 59, 68, 191-196, 205 — retry/error flows.
- `workers/redis_factory.py`: lines 25-102 — timeout handling and connection fallbacks.
- `workers/retrain_scheduler.py`: lines 22-26 — scheduling guards.
- `workers/runtime_scheduler.py`: lines 55-56 — boundary scheduling logic.
- `database/db_router.py`: lines 66-289 — DSN validation, RO fallback, and timeout handling.
- `services/predictor.py`: lines 27, 38-50 — deterministic seed paths and guard rails.
- `core/services/predictor.py`: lines 27, 38-50 — deterministic payload generation.
- `services/prediction_pipeline.py`: lines 39-40, 61, 90-91, 95, 165 — propagation of TTL/priority.
- `services/data_processor.py`: multiple paths 37-1456 — extensive gap (out of scope for current sprint).
- `scripts/train_model.py`: lines 3-839 — CLI orchestration paths untested (non-critical for current objective).

## After (pytest --cov=./ --cov-report=term-missing)

- `scripts/prestart.py`: добавлены негативные сценарии prestart (`test_prestart.py`), покрывающие отсутствующие переменные, провал Alembic и health-check Redis/Postgres.
- `telegram/handlers/*.py`: тесты ошибок `/predict`, `/match`, `/today` закрывают ветки валидации ввода и сообщений об ошибках.
- `telegram/widgets.py`: тесты экранирования HTML и форматирования процентов исключают XSS и NaN.
- `workers/queue_adapter.py`: покрыты маппинги редких статусов и безопасное формирование сообщений очереди.
- `workers/task_manager.py`: проверены TTL/priority при постановке задач и обработка исключений.
- `database/db_router.py`: проверены невалидные DSN, fallback RO→RW и ошибки стартового health-check.
- `core/services/predictor.py`: детерминизм по seed и отсутствие отрицательных/NaN значений.
- `scripts/prestart.py` и `workers/redis_factory.py`: гарантировано использование маскированных DSN/URL в логах.

### Delta summary

- Добавлено 8 новых модулей с целевыми тестами ошибок и валидации.
- Закрыты критичные ветки в `telegram`, `workers`, `database`, `services`, `scripts` пакетах.
- Расширены инфраструктурные утилиты (`queue_adapter`) без изменения бизнес-логики.

