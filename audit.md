/**
 * @file: audit.md
 * @description: Полный аудит текущего состояния бота перед адаптацией под Amvera.
 * @dependencies: см. ссылки на исходники по ходу документа.
 * @created: 2025-09-18
 */
# Аудит кода и документации

## Резюме
- Архитектура очередей и кэша жёстко завязана на конкретные реализации (`redis`/`rq`), отсутствует слой абстракции и изоляция соединений.
- ML-пайплайн и воркеры содержат несовместимые интерфейсы и прямые ошибки (несуществующие методы, `await` на синхронных функциях).
- Слой доступа к данным не соответствует целям продового деплоя на PostgreSQL: синхронный `psycopg2`, нет роутинга и Alembic.
- Команды бота и UX не соответствуют требованиям (нет /today, /match, /model; обработчики используют неподдерживаемые зависимости).
- CI/документация не покрывают Amvera (Dockerfile отсутствует, README описывает SQLite) и нет миграционных таргетов Makefile.

## A. Архитектура и зависимости

### A1. TaskManager жёстко связан с RQ/Redis (S)
- Прямые импорты `redis`, `rq`, глобальное состояние и логику подключения без адаптеров.【F:workers/task_manager.py†L7-L126】
- Логирует полный `REDIS_URL`, что недопустимо для прод-окружения с секретами.【F:workers/task_manager.py†L37-L43】
- Нет интерфейса очереди и инъекции зависимостей, нарушается требование изолировать очередь и позволить тестировать отказоустойчивость.

### A2. Хендлеры не совпадают с интерфейсом менеджера задач (S)
- `_start_prediction` вызывает `await enqueue_prediction(...)`, хотя в модуле объявлена совершенно другая функция (асинхронная обёртка, завязанная на `task_manager.add_task`, которого нет).【F:telegram/handlers/predict.py†L43-L456】
- В TaskManager отсутствует метод `add_task`, так что хендлеры никогда не смогут поставить задачу — критический провал UX.

### A3. Отсутствуют обязательные роутеры и команды (M)
- Регистрируются только `start`, `help`, `predict`; нет /today, /match, /model, требуемых постановкой задачи.【F:telegram/handlers/__init__.py†L5-L12】
- Нельзя расширить функциональность без серьёзного переписывания.

## B. ML-логика и пайплайн

### B1. RecommendationEngine использует несуществующие API (S)
- Импортируется `prediction_modifier` из `ml.modifiers_model`, но в файле нет такого объекта; `await self.modifier.apply_dynamic_modifiers` вызовет `AttributeError` в рантайме.【F:services/recommendation_engine.py†L25-L188】【F:ml/modifiers_model.py†L1-L48】
- `generate_comprehensive_prediction` ожидает один аргумент, воркер передаёт два, что приведёт к TypeError.【F:services/recommendation_engine.py†L166-L196】【F:workers/prediction_worker.py†L121-L139】

### B2. PredictionWorker нарушает контракт модели (S)
- Воркер `await`-ит синхронный метод `poisson_regression_model.load_ratings`, что мгновенно поднимет `TypeError` при запуске.【F:workers/prediction_worker.py†L55-L60】【F:ml/models/poisson_regression_model.py†L55-L82】
- Использует Redis-лок без проверок таймаута/исключений, но главное — зависит от глобального `cache`, который может быть `None` (см. раздел D).

### B3. Предсказатель не гарантирует инварианты (M)
- `compute_probs` опирается на `ml.models.poisson_model`, которого нет в дереве, возвращает пустой словарь; значит дальнейшие шаги (confidence, рекомендации) работают с нулями.【F:telegram/handlers/predict.py†L56-L112】
- `generate_full_prediction` обильно опирается на заглушки (`data_processor`, `apply_weather_field`) без проверок NaN/отрицательных λ, риск некорректных вероятностей.【F:telegram/handlers/predict.py†L205-L332】

## C. Данные и доступ к БД

### C1. Слой БД не соответствует целям (S)
- `database/db_logging.py` использует синхронный `psycopg2.SimpleConnectionPool` и блокирующие вызовы, невозможные в асинхронном Telegram-боте.【F:database/db_logging.py†L6-L200】
- Нет разделения RW/RO, параметры берутся напрямую из ENV, не поддерживая PostgreSQL на Amvera с несколькими DSN.

### C2. Нет универсального роутера и Alembic (S)
- В репозитории только ручной SQL-скрипт, нет `alembic.ini`/`env.py`, что делает миграции инициализации невозможными на Amvera.【F:database/migrations/001_create_predictions.sql†L1-L86】
- Makefile не содержит таргетов `migrate/upgrade/downgrade`, подтверждая отсутствие автоматизации миграций.【F:Makefile†L16-L68】

### C3. Конфиг не маскирует секреты и противоречив (M)
- `ODDS_API_KEY` помечен как обязательный, но имеет пустое значение по умолчанию — валидатор никогда не сработает.【F:config.py†L14-L34】
- Глобальный `settings = get_settings()` выполняется при импорте, что затрудняет тестирование и подмену окружения.【F:config.py†L142-L169】

## D. Очереди и кэш

### D1. Redis-клиенты создаются неконтролируемо (S)
- `database/cache.py` инициализирует клиент при импорте, логирует полный URL и не поддерживает повторное подключение.【F:database/cache.py†L16-L169】
- Слой `cache_postgres` хранит глобальные переменные, `fetch_lineup_api` — заглушка, возвращающая `None`, поэтому кэш лайнапов никогда не заполняется.【F:database/cache_postgres.py†L21-L257】

### D2. Глобальный `cache` не гарантирован (M)
- `telegram/handlers/predict.py` ожидает, что `cache` уже проинициализирован, иначе `await cache.set(...)` вызовет `AttributeError`. Инициализация зависит от ручного вызова `init_cache` в разных местах.【F:telegram/handlers/predict.py†L329-L338】【F:database/cache_postgres.py†L251-L260】

## E. Бот и UX

### E1. Команда /predict нерабочая (S)
- Вместо постановки задачи через TaskManager вызывается несуществующий метод `task_manager.add_task`, поэтому RQ ничего не получит.【F:telegram/handlers/predict.py†L443-L456】【F:workers/task_manager.py†L73-L176】
- Отсутствует полноценная валидация ввода (разные тире, локали), требований постановки не выполняются.

### E2. Отсутствуют ключевые команды и обработчики (M)
- Нет команд /today, /match <id>, /model: документация и стартовый UX этого не предусматривают, маршрутизация ограничена меню.【F:telegram/handlers/__init__.py†L5-L12】【F:telegram/handlers/start.py†L91-L178】

## F. Логи, безопасность, наблюдаемость

### F1. Логи раскрывают секреты (S)
- Логирование Redis DSN в явном виде (`logger.info(f"... {redis_url}")`) в `cache.py` и `TaskManager`. Это нарушает требования маскирования на проде.【F:database/cache.py†L21-L29】【F:workers/task_manager.py†L37-L43】

### F2. Нет структурных логов с версиями (M)
- Основные точки входа (`main.py`, `workers/prediction_worker.py`) не добавляют `app_version`/`git_sha` в поля логов, отсутствуют корелляционные метаданные.【F:main.py†L19-L50】【F:workers/prediction_worker.py†L41-L143】

## G. CI/CD и деплой

### G1. README не отражает переход на PostgreSQL/Amvera (M)
- Документация продолжает описывать хранение прогнозов в SQLite и офлайн сценарии, ни слова про Amvera, alembic upgrade и пуш в Amvera-репозиторий.【F:README.md†L51-L112】

### G2. Отсутствует Dockerfile и entrypoint (S)
- В корне проекта нет Dockerfile/entrypoint для Amvera, текущий Makefile не готовит образ и не выполняет alembic при старте (см. отсутствие упоминаний в Makefile).【F:Makefile†L16-L68】

### G3. Тесты не покрывают критические сценарии (M)
- Нет тестов на отказоустойчивость TaskManager (enqueue/status/cancel), на Redis фабрику, на DB-роутер; существующий `tests/test_task_manager_cleanup.py` покрывает только очистку очереди.【F:tests/test_task_manager_cleanup.py†L1-L55】

## H. Документация

### H1. CHANGELOG и Tasktracker устарели (L)
- Последние записи касаются Redis-кэша и не отражают найденные проблемы ни по Amvera, ни по очередям.【F:docs/changelog.md†L1-L24】【F:docs/tasktracker.md†L1-L40】

---

**Приоритеты исправления:** сначала устранить критические ошибки (S) в очередях, воркерах и БД, затем привести UX и документацию в соответствие (M), после чего закрыть оставшиеся организационные пробелы (L).
