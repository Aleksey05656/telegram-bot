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

## ML stack

- numpy >=1.26,<2.0
- pandas ==2.2.2

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

## Local model registry

`app/ml/model_registry.py` сохраняет модели на файловой системе. По умолчанию используется каталог
`artifacts/`, который можно переопределить переменной окружения `MODEL_REGISTRY_PATH`.

## SportMonks stub mode

Режим заглушки включается, если установить `SPORTMONKS_STUB=1` или оставить `SPORTMONKS_API_KEY`
пустым/`dummy`. Для реального API необходимо задать ключ и выставить `SPORTMONKS_STUB=0`.

## Key environment variables

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота.
- `SPORTMONKS_API_KEY` — ключ API SportMonks.
- `SPORTMONKS_STUB` — `1` включает заглушечные ответы SportMonks.
- `MODEL_REGISTRY_PATH` — каталог LocalModelRegistry (по умолчанию `artifacts/`).
- `RETRAIN_CRON` — crontab для планировщика (пусто/`off` выключает).
- `SEASON_ID` — сезон для скрипта обучения (по умолчанию `23855`).


## Тесты без NumPy/Pandas (офлайн/прокси)

Если `numpy` и `pandas` недоступны (например, в офлайн окружении),
тесты, помеченные `@pytest.mark.needs_np` или подпадающие под шаблоны
`test_ml.py`, `test_services.py`, `test_metrics.py`, `test_prediction`
будут автоматически пропущены.
Шаблоны можно переопределить переменной окружения:

```bash
NEEDS_NP_PATTERNS="test_ml.py|test_services.py" pytest -q
```

В CI переменная `NEEDS_NP_PATTERNS` уже выставлена автоматически.

## Tests

- Контрактный тест сверяет `.env.example` с `app.config.Settings`.
- E2E тест проверяет `PredictionPipeline` вместе с `LocalModelRegistry`.
- Smoke-тест гарантирует, что `TaskManager.cleanup` не падает без Redis.

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
