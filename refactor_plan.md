/**
 * @file: refactor_plan.md
 * @description: План работ по приведению бота к прод-готовности на Amvera.
 * @dependencies: audit.md, требования из постановки.
 * @created: 2025-09-18
 */
# План рефакторинга

## Обозначения
- **Оценка трудозатрат:** S ≤ 0.5 дня, M ≈ 1 день, L ≥ 2 дней.
- **Риск:** S — высокий, M — средний, L — низкий (соответствует влиянию на прод).
- **Критерии приёмки** формулируются для каждого этапа.

## E1. Унифицированный слой БД (Async SQLAlchemy)
- **Суть:** Реализовать `DBRouter` с поддержкой SQLite (dev) и PostgreSQL RW/RO, добавить Alembic и миграционные таргеты Makefile.
- **Декомпозиция:**
  1. Написать `database/db_router.py` с инициализацией `AsyncEngine`, session factory и shutdown.
  2. Добавить Alembic scaffold (`alembic.ini`, `env.py`, первая версия из существующего SQL`).
  3. Обновить Makefile (`make migrate/upgrade/downgrade`) и интегрировать prestart `alembic upgrade head`.
- **Критерии приёмки:**
  - Тесты `tests/database/test_db_router.py` покрывают выбор схемы, RO/RW, таймауты, обработку ошибок.
  - Alembic успешно накатывает миграцию на локальной SQLite и на PostgreSQL (через CI stub).
  - Локальный запуск (`make migrate && pytest`) зелёный.
- **Трудозатраты:** L.
- **Риск:** S (без этого Amvera недоступна).

## E2. Фабрика Redis и адаптер очереди
- **Суть:** Вынести создание Redis-клиента и очередь RQ в отдельные абстракции с backoff/health-check.
- **Декомпозиция:**
  1. Создать `database/redis_connection.py` (async ping, маскирование URL, retry).
  2. Написать `workers/queue_adapter.py` с протоколом `IQueueAdapter`, реализацией для RQ и маппингом статусов.
  3. Обновить `workers/task_manager.py`, чтобы он использовал DI (`DBRouter`, Redis factory, QueueAdapter) и перестал логировать секреты.
- **Критерии приёмки:**
  - Новые тесты `tests/workers/test_redis_connection.py` и `tests/workers/test_queue_adapter.py` проверяют ping/backoff, TTL, маппинг статусов.
  - Логи маскируют DSN, `TaskManager` не держит глобальные соединения.
- **Трудозатраты:** M.
- **Риск:** S.

## E3. Исправление Telegram-хендлеров и UX
- **Суть:** Переписать `/predict` и сопутствующие команды, добавить /today, /match, /model согласно требованиям.
- **Декомпозиция:**
  1. Создать `workers/utils.py` для валидации команд, TTL/priority.
  2. Обновить `telegram/handlers` (predict/today/match/model/help/start) с DI сервисов, безопасным HTML-эскейпингом.
  3. Обновить `RecommendationService`/`TaskManager` интеграцию (использовать адаптер, возвращать job_id).
- **Критерии приёмки:**
  - Smoke-тест `/help`, `/model`, `/predict` проходит (новый `@pytest.mark.bot_smoke`).
  - `/predict` ставит задачу через адаптер и возвращает job_id.
  - Команды обрабатывают разные разделители, ошибки локализованы.
- **Трудозатраты:** L.
- **Риск:** S (критичная функциональность).

## E4. ML-пайплайн и воркеры
- **Суть:** Согласовать интерфейсы PredictionWorker, RecommendationEngine и pipeline.
- **Декомпозиция:**
  1. Исправить `services/recommendation_engine` (убрать несуществующие импорты, сделать синхронные части async-aware, добавить проверки NaN/λ≥0).
  2. Обновить `workers/prediction_worker.py` (правильные await, DI сервисов, использование QueueAdapter и Redis factory).
  3. Добавить smoke-тесты воркера (`tests/workers/test_task_manager.py`).
- **Критерии приёмки:**
  - `pytest -k workers` зелёный; покрытие workers/* ≥90%.
  - `RecommendationEngine` возвращает нормализованные вероятности (1X2 суммируется до 1 ±1e-6).
- **Трудозатраты:** L.
- **Риск:** S.

## E5. Docker, entrypoint и health-check
- **Суть:** Подготовить production-ready образ и startup sequence для Amvera.
- **Декомпозиция:**
  1. Добавить multi-stage `Dockerfile` и `.dockerignore`.
  2. Написать `scripts/entrypoint.sh` (env check, alembic upgrade, health-check Redis/Postgres, запуск бота).
  3. Обновить Makefile/README с инструкциями `docker build`, `docker run`, push в Amvera.
- **Критерии приёмки:**
  - Локальный `docker build` проходит; `docker run` запускает бота после успешного health-check.
  - Health-check падает при недоступности Redis/Postgres с осмысленной ошибкой.
- **Трудозатраты:** M.
- **Риск:** S.

## E6. Тестовое покрытие и CI
- **Суть:** Расширить pytest-набор под новые компоненты и обновить CI инструкции.
- **Декомпозиция:**
  1. Добавить тесты: `tests/workers/test_task_manager.py`, `tests/workers/test_queue_adapter.py`, `tests/database/test_db_router.py` (см. E1/E2/E4).
  2. Расширить smoke: `/today`, `/match`, `/model` с моками ядра.
  3. Обновить `pytest.ini`/Makefile цели (coverage threshold ≥80% проекта, ≥90% для workers/database).
- **Критерии приёмки:**
  - `pytest` и coverage проходят в CI; отчёт ≥80/90.
  - Новые тесты документированы в README и changelog.
- **Трудозатраты:** M.
- **Риск:** M.

## E7. Документация и секреты
- **Суть:** Синхронизировать README, CHANGELOG, Project.md, Tasktracker и маскирование секретов.
- **Декомпозиция:**
  1. Обновить README (локальный запуск vs Amvera, env переменные, Alembic, push-процесс).
  2. Добавить новые разделы в `docs/changelog.md` и `docs/tasktracker.md` (прогресс, чек-лист).
  3. Обновить `docs/Project.md` (диаграмма слоёв с DBRouter/QueueAdapter).
- **Критерии приёмки:**
  - Документация описывает Amvera deploy, переменные окружения и health-check.
  - Changelog/Tasktracker отражают завершённые этапы; Project.md актуален.
- **Трудозатраты:** M.
- **Риск:** M.

## Риск-матрица

| Этап | Риск | Митигаторы |
|------|------|------------|
| E1 | S | Использовать SQLAlchemy best practices, покрыть тестами все схемы DSN. |
| E2 | S | Ввести backoff и таймауты, unit-тесты на провалы подключения. |
| E3 | S | Пошаговые smoke-тесты команд, feature flags для новых команд. |
| E4 | S | Интеграционные тесты воркера, проверка инвариантов вероятностей. |
| E5 | S | Локальный `docker run`, автоматический health-check перед запуском бота. |
| E6 | M | Разделение тестов по маркерам, запуск в CI. |
| E7 | M | Code review документации, чек-лист секретов. |

## Зависимости между этапами
1. **E1 → E2/E4/E5**: DBRouter нужен до переработки воркеров и entrypoint.
2. **E2 → E3/E4**: очередь и Redis фабрика должны быть готовы до обновления хендлеров и воркеров.
3. **E3/E4 → E6**: после переписывания функционала обновляем тесты и coverage.
4. **E5 → E7**: Docker/entrypoint влияют на документацию.

## Итоговая последовательность
1. E1 (БД) → 2. E2 (Redis/Queue) → 3. E4 (воркеры) параллельно с подготовкой утилит (E3 частично) → 4. Завершение E3 (бот/UX) → 5. E6 (тесты/coverage) → 6. E5 (Docker/entrypoint) → 7. E7 (доки, changelog/tasktracker).
