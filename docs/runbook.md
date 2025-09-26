<!--
@file: docs/runbook.md
@description: Operations runbook for monitoring alerts.
@created: 2025-10-29
-->

# Monitoring Runbook

## Data Freshness RED
- Проверить состояние токена и квот SportMonks (панель провайдера, `SPORTMONKS_*` переменные).
- Изучить логи `sm_sync` / `scripts/sm_sync.py` на признаки таймаутов или rate-limit.
- Убедиться, что воркер активен, при необходимости перезапустить роль `worker` после устранения причин.

## Worker Deadman
- Проверить доступность Redis и PostgreSQL, убедиться, что очередь/lock-сервис отвечает.
- Осмотреть lock-файл `/data/runtime.lock`, удалить, если он stale и процесс не работает.
- Перезапустить воркер (`python -m scripts.worker` или профиль Amvera) после очистки зависимостей.

## API Readiness 503
- Убедиться, что `PRESTART_PREFLIGHT=1` и последний прогон preflight завершился успешно.
- Запросить `/readyz` вручную, изучить подробности ответа (`status`, `checks`).
- Проверить подключение к PostgreSQL/Redis, восстановить доступность сервисов и перезапустить роль `api`.

## Odds stalled
- Проверить провайдера котировок и сетевые таймауты в логах `services/odds`.
- Увеличить `ODDS_TIMEOUT_SEC` или число ретраев, если наблюдаются частые timeouts.
- Убедиться, что внешние матчи доступны и нет глобального простоя провайдера.
