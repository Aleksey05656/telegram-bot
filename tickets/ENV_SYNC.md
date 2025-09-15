<!--
@file: ENV_SYNC.md
@description: Missing environment variables in .env.example
@dependencies: app/config.py, tests/conftest.py, app/main.py, workers/retrain_scheduler.py
@created: 2025-09-15
-->

# ENV Sync

The following variables are absent from `.env.example`:

- `ENV` – expected application environment; no direct reference found.
- `PROMETHEUS__ENABLED` – required by tests (`tests/conftest.py:58`).
- `PROMETHEUS__ENDPOINT` – expected alias for metrics endpoint.
- `RETRAIN_CRON` – used in `app/main.py:41`, `workers/retrain_scheduler.py:43`, and `tests/smoke/test_retrain_registration.py:22`.
