<!--
@file: README.md
@description: Project description and quick start
@dependencies: requirements.txt, Makefile
@created: 2025-09-10
-->

# Telegram Bot

Telegram bot that exposes a FastAPI service and ML pipeline for football match predictions.

## Quick start

```bash
cp .env.example .env
make setup
make check
```

See [ARCHITECTURE.md](ARCHITECTURE.md) and `docs/Project.md` for more details.

## Services & Workers (скелеты)

Добавлены минимальные заготовки для боевого включения без падений в ограниченных окружениях:

- `services/prediction_pipeline.py` — продовый фасад предсказаний:
  - интерфейсы `Preprocessor`, `ModelRegistry`;
  - заглушечная модель, если реестр не доступен;
  - устойчив к отсутствию `numpy/pandas` (вернёт список списков).

- `workers/retrain_scheduler.py` — регистрация периодического переобучения:
  - `schedule_retrain(register, cron_expr=None, task=None)`;
  - читает `RETRAIN_CRON` из окружения (по умолчанию `0 3 * * *`);
  - ленивая подгрузка тренера для избежания тяжёлых импортов.

Быстрая проверка:
```bash
pytest -q -k test_services_workers_minimal
```

> Тесты помечены `@pytest.mark.needs_np`: при недоступном численном стеке будут SKIP.

## Retrain scheduler (feature-flag)

Встроена «лёгкая» интеграция планировщика:

- **ENV-флаг**: `RETRAIN_CRON`
  - пусто / `off` / `disabled` / `none` / `false` → **планировщик выключен**;
  - любое корректное выражение crontab → регистрируется задача переобучения.
- **Адаптер**: in-memory `workers/runtime_scheduler.py` (для smoke/локалки).
- **Эндпоинт**: `GET /__smoke__/retrain` — статус регистрации: enabled/count/crons.

Быстрая проверка:
```bash
RETRAIN_CRON="*/15 * * * *" uvicorn app.main:app --reload &
curl -s http://127.0.0.1:8000/__smoke__/retrain
```

Тест:
```bash
pytest -q -k test_retrain_registration
```

## Smart pre-commit fallback

Если обычный `pre-commit` упирается в прокси/GitHub (например, `CONNECT tunnel failed, response 403`),
запустите:
```bash
make pre-commit-smart
```
Цель сначала пробует обычный конфиг (онлайн), а при сетевой ошибке автоматически переключается на
локальный `.pre-commit-config.offline.yaml` (без внешних загрузок). Кеш хуков находится в `$(PRE_COMMIT_HOME)`
и по умолчанию — `.cache/pre-commit`.

Точно так же можно запускать на части файлов:
```bash
PRECOMMIT=pre-commit PRE_COMMIT_HOME=.cache/pre-commit python scripts/run_precommit.py run --files path/to/file.py README.md
```
