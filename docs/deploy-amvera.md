<!--
@file: docs/deploy-amvera.md
@description: Amvera deployment guide for Telegram bot
@dependencies: README.md, amvera.yaml
@created: 2025-10-03
-->

# Руководство по деплою на Amvera

## 1. Требования платформы
- **amvera.yaml** описывает окружение `python/pip 3.11`, точку входа `main.py`, монтирование `/data`.
- Все изменяемые данные (`DB_PATH`, `MODEL_REGISTRY_PATH`, `REPORTS_DIR`, `LOG_DIR`) должны находиться под `/data`.
- Переменные окружения и секреты задаются в UI Amvera; во время сборки недоступны.
- Для Telegram long polling добавлена задержка `BOT_STARTUP_DELAY` (2.5 c) и флаг `--dry-run` для smoke.
- Логи должны идти без буферизации (`PYTHONUNBUFFERED=1`).
- Серверное время — UTC; конвертацию делайте в клиенте/репортах при необходимости.

## 2. Обязательные переменные окружения
| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Токен бота из BotFather | — (обязателен) |
| `DATABASE_URL` | Async DSN writer (Postgres) | — |
| `DATABASE_URL_RO` | Async DSN чтения (опционально) | — |
| `DATABASE_URL_R` | DSN реплики (опционально) | — |
| `REDIS_URL` | Redis в Amvera (если используется) | — |
| `APP_VERSION` | Версия релиза (для логов/метрик) | — |
| `GIT_SHA` | Commit SHA (для трассировки) | — |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `DB_PATH` | SQLite fallback | `/data/bot.sqlite3` |
| `MODEL_REGISTRY_PATH` | Каталог артефактов моделей | `/data/artifacts` |
| `REPORTS_DIR` | Каталог отчётов и markdown | `/data/reports` |
| `LOG_DIR` | Каталог логов (RotatingFileHandler) | `/data/logs` |
| `RUNTIME_LOCK_PATH` | Путь для lock-файла единственного инстанса | `/data/runtime.lock` |
| `ENABLE_HEALTH` | Флаг запуска встроенного `/health` | `0` |
| `HEALTH_HOST` / `HEALTH_PORT` | Адрес и порт health-сервера | `0.0.0.0` / `8080` |
| `BOT_STARTUP_DELAY` | Задержка перед polling (секунды) | `2.5` |
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

## 7. Health-probe
- Включается переменной `ENABLE_HEALTH=1` (см. `amvera.yaml`, порт 8080).
- Сервер отвечает на `GET /health` со статусом `200 OK` и JSON `{"status":"ok"}`; другие методы возвращают 405/404.
- Подходит для probe из Amvera или внешнего ALB. При выключенном флаге сервер не стартует.

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
- Для API Telegram следите за статусами 429 — увеличьте задержку `BOT_STARTUP_DELAY` или подключите прокси.
- При ошибках Redis проверьте доступность `REDIS_URL` и политику firewall.

## 11. Перенос существующей SQLite
1. На старом окружении остановите бота и убедитесь, что SQLite не меняется.
2. Скопируйте файл в безопасное место: `scp bot.sqlite3 ops@host:/tmp/bot.sqlite3`.
3. В Amvera откройте **Repository → Data**, создайте каталог `data` (если нет) и загрузите файл как `bot.sqlite3`.
4. Проверьте права доступа: файл должен принадлежать пользователю приложения и находиться по пути `/data/bot.sqlite3`.
5. Обновите переменную `DB_PATH`, если имя файла отличается.

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
| `double getUpdates` / бот отключается | Несколько инстансов без задержки | Убедитесь, что `BOT_STARTUP_DELAY` > 0 и только один контейнер активен. |
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
