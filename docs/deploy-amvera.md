<!--
@file: docs/deploy-amvera.md
@description: Amvera deployment guide for Telegram bot
@dependencies: README.md, amvera.yaml
@created: 2025-10-03
-->

# Руководство по деплою на Amvera

## 1. Требования платформы
- **amvera.yaml** описывает окружение `python/pip 3.11`, роли `api|worker|tgbot` с запуском `uvicorn app.api:app` для API и монтирование `/data`.
- Все изменяемые данные (`DB_PATH`, `MODEL_REGISTRY_PATH`, `REPORTS_DIR`, `LOG_DIR`) должны находиться под `/data`.
- Переменные окружения и секреты задаются в UI Amvera; во время сборки недоступны.
- Для Telegram long polling используется флаг `STARTUP_DELAY_SEC` (по умолчанию 0 c) и флаг `--dry-run` для smoke.
- Логи должны идти без буферизации (`PYTHONUNBUFFERED=1`).
- Серверное время — UTC; конвертацию делайте в клиенте/репортах при необходимости.

## 2. Обязательные переменные окружения
| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Токен бота из BotFather | — (обязателен) |
| `DATABASE_URL` | Async DSN writer (Postgres). При отсутствии собирается из `PGUSER`/`PGPASSWORD`/`PGDATABASE`/`PGHOST_RW`/`PGPORT`. | — |
| `DATABASE_URL_RO` | Async DSN чтения (опционально, fallback к `PGHOST_RO`). | — |
| `DATABASE_URL_R` | DSN реплики (опционально, fallback к `PGHOST_RR`). | — |
| `PGUSER` / `PGPASSWORD` / `PGDATABASE` / `PGHOST_RW` / `PGHOST_RO` / `PGHOST_RR` / `PGPORT` | Компоненты для сборки DSN, если `DATABASE_URL*` не заданы. | — |
| `REDIS_URL` | Redis в Amvera (если используется). Приоритетная переменная. | — |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD` | Fallback-параметры для сборки `REDIS_URL`. | — |
| `SPORTMONKS_API_TOKEN` | Основной API-токен SportMonks | — |
| `SPORTMONKS_TOKEN` / `SPORTMONKS_API_KEY` | Устаревшие синонимы токена (при использовании логируется предупреждение) | — |
| `APP_VERSION` | Версия релиза (для логов/метрик) | — |
| `GIT_SHA` | Commit SHA (для трассировки) | — |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `DB_PATH` | SQLite fallback | `/data/bot.sqlite3` |
| `MODEL_REGISTRY_PATH` | Каталог артефактов моделей | `/data/artifacts` |
| `REPORTS_DIR` | Каталог отчётов и markdown | `/data/reports` |
| `LOG_DIR` | Каталог логов (RotatingFileHandler) | `/data/logs` |
| `RUNTIME_LOCK_PATH` | Путь для lock-файла единственного инстанса | `/data/runtime.lock` |
| `ENABLE_HEALTH` | Legacy TCP health-сервер (по умолчанию выключен; основная проверка — `/healthz` и `/readyz` в API) | `0` |
| `HEALTH_HOST` / `HEALTH_PORT` | Адрес и порт legacy health-сервера | `0.0.0.0` / `8080` |
| `ENABLE_METRICS` | Prometheus-метрики на `/metrics` (порт API) | `0` |
| `METRICS_PORT` | Дополнительный порт для внутренних скрейпов (не пробрасывается наружу) | `8000` |
| `STARTUP_DELAY_SEC` | Задержка перед polling (секунды) | `0` |
| `ENABLE_POLLING` | Запуск Telegram polling | `1` |
| `ENABLE_SCHEDULER` | Регистрация задач переобучения/обслуживания | `1` |
| `FAILSAFE_MODE` | Отключить тяжёлые фоновые задачи (maintenance/retrain) | `0` |
| `BACKUP_DIR` / `BACKUP_KEEP` | Каталог и глубина ротации SQLite-бэкапов | `/data/backups` / `10` |
| `PYTHONUNBUFFERED` | Небуферизованные логи | `1` |
| `SHUTDOWN_TIMEOUT` | Таймаут graceful shutdown (секунды) | `30` |
| `RETRY_ATTEMPTS` / `RETRY_DELAY` / `RETRY_MAX_DELAY` / `RETRY_BACKOFF` | Параметры экспоненциальных ретраев | `3` / `1.0` / `8.0` / `2.0` |
| `RETRAIN_CRON` | Планировщик переобучений (или `off`) | `0 3 * * *` |

## 3. Подготовка окружения
1. Создайте приложение на Amvera и смонтируйте persistence (по умолчанию `/data`).
2. Заполните переменные окружения по таблице выше.
3. Убедитесь, что директория `/data` пуста либо содержит мигрированные данные SQLite (см. раздел 11).
4. При необходимости загрузите модели/отчёты в каталог `/data/artifacts` через вкладку **Repository → Data**.

## 4. CI и smoke-проверка
- GitHub Actions содержит job `amvera-smoke`, который выполняет `python -m main --dry-run` c временным `DB_PATH`/`REPORTS_DIR`.
- Дополнительная job `amvera-ops-v2-smoke` запускает `python -m main --dry-run` с `ENABLE_METRICS=1`, затем проверяет `/healthz`, `/readyz` (алиасы `/health`, `/ready` остаются) и `/metrics` curl-запросами.
- Локально перед деплоем выполните:
  ```bash
  export DB_PATH=$(mktemp -u)
  export REPORTS_DIR=$(mktemp -d)
  export PYTHONUNBUFFERED=1
  python -m main --dry-run
  ```
  Команда проверит инициализацию зависимостей без запуска polling.

## 5. Graceful shutdown
- Обработчики `SIGTERM`/`SIGINT` переводят приложение в состояние завершения, вызывая `TelegramBot.stop()` и ожидая закрытие polling.
- Таймаут регулируется переменной `SHUTDOWN_TIMEOUT` (по умолчанию 30 секунд). В логах появится предупреждение, если граница превышена.
- Перед выходом вызывается `shutdown_cache()` и очищаются задания планировщика (`workers.runtime_scheduler.clear_jobs`).
- Рекомендуется завершать контейнер командой `docker stop`, чтобы Amvera послала `SIGTERM`.

## 6. Single instance
- `app/runtime_lock.py` создаёт lock-файл (`RUNTIME_LOCK_PATH`, дефолт `/data/runtime.lock`).
- При старте второго экземпляра выводится сообщение «Приложение уже запущено» без stack trace — процесс завершится корректно.
- Размещение lock-файла в `/data` гарантирует совместимость с Amvera persistence.
- Проверьте права записи, если контейнер работает под не-root пользователем.

## 7. Health / Readiness probes
- API всегда отдаёт `GET /healthz` (алиас `/health`) с `200 OK` и `{"status":"ok"}`.
- `GET /readyz` (алиас `/ready`) выполняет `SELECT 1` в Postgres, `PING` в Redis и проверяет флаги планировщика/бота. Успешный ответ — `200` с `status=ok`, деградация — `200` с `status=degraded`, критическая ошибка — `503`.
- Переменная `ENABLE_HEALTH=1` включает legacy TCP-сервер (`HEALTH_HOST`/`HEALTH_PORT`); основной сценарий Amvera использует HTTP-эндпоинты FastAPI.

## 8. Logs & retention
- Логгер использует `RotatingFileHandler` с ротацией 10 МБ × 5 файлов (`/data/logs/app.log` + бэкапы).
- Форматы: JSON для файлов, logfmt для stdout. Переключение уровня — переменная `LOG_LEVEL`.
- `PYTHONUNBUFFERED=1` обязателен: stdout/stderr сразу уходит в Amvera logging.
- При dry-run и smoke-командах выполняется проверка записи в `LOG_DIR`/`REPORTS_DIR`/`MODEL_REGISTRY_PATH`.

## 9. ENV-контракт
- `.env.example` содержит все переменные, которые читает код через `os.environ[...]`/`Settings`.
- Тест `tests/test_env_contract.py` гарантирует синхронизацию: при добавлении новой переменной обновляйте `.env.example` и документацию.
- В `docs/tasktracker.md` фиксируйте изменения окружения для traceability.

## 10. Отладка 429/5xx/таймаутов
- Сетевые операции (инициализация Redis, Telegram API) обёрнуты в `retry_async` с экспоненциальным бэкоффом. Параметры изменяются через `RETRY_*`.
- В логах видно попытки повторов (`Retrying <fn> in X.XXs`). Если превышен лимит, запись `Retry attempts exhausted` поможет локализовать узкое место.
- Для API Telegram следите за статусами 429 — увеличьте `STARTUP_DELAY_SEC` или подключите прокси.
- При ошибках Redis проверьте доступность `REDIS_URL` и политику firewall.

## 11. Перенос существующей SQLite
1. На старом окружении остановите бота и убедитесь, что SQLite не меняется.
2. Скопируйте файл в безопасное место: `scp bot.sqlite3 ops@host:/tmp/bot.sqlite3`.
3. В Amvera откройте **Repository → Data**, создайте каталог `data` (если нет) и загрузите файл как `bot.sqlite3`.
4. Проверьте права доступа: файл должен принадлежать пользователю приложения и находиться по пути `/data/bot.sqlite3`.
5. Обновите переменную `DB_PATH`, если имя файла отличается.
6. Планировщик делает ежедневные бэкапы в `BACKUP_DIR` (по умолчанию `/data/backups`) и хранит не более `BACKUP_KEEP` файлов. Для восстановления достаточно остановить контейнер, скопировать нужный `bot-*.sqlite3` в `DB_PATH` и запустить приложение.
7. Раз в неделю выполняется `VACUUM/ANALYZE` — операция блокирует SQLite на несколько секунд; включайте `FAILSAFE_MODE=1`, если обслуживающие задачи нужно отключить.
8. Все соединения к SQLite открываются в режиме WAL (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`).

## 12. Сценарии доставки кода
### 6.1 Git push в репозиторий Amvera
1. Добавьте удалённый репозиторий: `git remote add amvera ssh://git@amvera.example.com/telegram-bot.git`.
2. Выполните `git push amvera main` (или выбранную ветку). Платформа автоматически запустит сборку и деплой.

### 6.2 Вебхук из GitHub/GitLab
1. Создайте персональный токен в Amvera (раздел Integrations → Webhooks).
2. Настройте webhook на стороне GitHub/GitLab на событие `push` (или `workflow_run` после успешного CI).
3. Укажите endpoint из Amvera, добавьте токен в заголовок `X-Amvera-Token`.
4. Проверьте, что webhook триггерит сборку и отображается в журнале.

## 13. Процесс деплоя
1. Обновите `main` (или release-ветку) через PR, дождитесь зелёного CI (lint, tests, `amvera-smoke`).
2. Выполните git push или дождитесь webhook-а (раздел 12).
3. В Amvera мониторьте логи сборки; убедитесь, что `pip install` завершился успешно.
4. После старта контейнера проверьте логи приложения (`/data/logs/app_*.json.log`).
5. Запустите smoke-команду в контейнере при необходимости: `python -m main --dry-run`.
6. Выполните ручной тест бота (команды `/start`, `/predict`).

## 14. Откат и пересборка
- Для отката выберите предыдущий билд в интерфейсе Amvera и нажмите **Rollback**.
- При пересборке без изменения кода выполните `git commit --allow-empty -m "chore: rebuild"` и push, либо перезапустите билд в UI.
- При сбоях удаления данных: восстановите `/data` из резервной копии (см. раздел 11) и перезапустите контейнер.

## 15. Типовые ошибки и диагностика
| Симптом | Причина | Диагностика |
| --- | --- | --- |
| `double getUpdates` / бот отключается | Несколько инстансов без задержки | Убедитесь, что `STARTUP_DELAY_SEC` > 0 и только один контейнер активен. |
| `sqlite is readonly` | Файл находится вне `/data` | Проверьте переменную `DB_PATH`, права и расположение файла. |
| Нет логов в UI | Отсутствует `PYTHONUNBUFFERED` | Установите переменную в окружении и перезапустите контейнер. |
| Ошибки Redis | `REDIS_URL` не задан или неверный | Проверьте переменную в UI, выполните `redis-cli PING` из контейнера. |
| `TELEGRAM_BOT_TOKEN` отсутствует | Бот завершается сразу | Заполните переменную и перезапустите приложение. |

См. официальные руководства Amvera:
- [docs.amvera.ru/platform/storage](https://docs.amvera.ru/platform/storage)
- [docs.amvera.ru/platform/variables](https://docs.amvera.ru/platform/variables)
- [docs.amvera.ru/platform/telegram-bot](https://docs.amvera.ru/platform/telegram-bot)
- [docs.amvera.ru/platform/sqlite](https://docs.amvera.ru/platform/sqlite)

## 16. Чек-лист релиз-менеджера
- [ ] SQLite перенесена в `/data` и указана в `DB_PATH`.
- [ ] Переменные окружения актуализированы (см. таблицу).
- [ ] Выполнен `python -m main --dry-run` (локально и в CI).
- [ ] Проверены логи `/data/logs`. Убедиться в наличии строк запуска.
- [ ] Команды `/start`, `/model`, `/predict` отвечают корректно.
- [ ] Сохранены артефакты моделей `/data/artifacts`.

## 17. Профиль Telegram-воркера
- **Исполняемый скрипт**: `python scripts/tg_bot.py`
- **Префлайт перед релизом** (опционально): `python scripts/preflight_worker.py`
- **Ключевые переменные окружения**: `ROLE=bot`, `TELEGRAM_BOT_TOKEN`, `PYTHONUNBUFFERED=1`, `LOG_LEVEL=INFO`, `PYTHONPATH=.`
- **Ожидаемые стартовые логи**: строка `tg_bot bootstrap: ROOT=... PYTHONPATH=...` и отсутствие ошибок `ModuleNotFoundError: telegram.middlewares`.
