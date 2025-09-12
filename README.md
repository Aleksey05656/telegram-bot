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
