# Static Audit

## Compile Check
The following Python files failed to compile due to invalid header comments using `/**` style:
- telegram/middlewares.py
- telegram/models.py
- ml/calibration.py
- ml/modifiers_model.py
- ml/montecarlo_simulator.py
- ml/base_poisson_glm.py
- app/data_processor/__init__.py
- app/data_processor/feature_engineering.py
- app/data_processor/io.py
- app/data_processor/transformers.py
- app/data_processor/validators.py

## ENV Contract
Settings expect many variables (e.g., `TELEGRAM_BOT_TOKEN`, `SPORTMONKS_API_KEY`, `ODDS_API_KEY`, `DATABASE_URL`, `CACHE_VERSION`, etc.) that are absent from `.env.example`. Conversely, `.env.example` defines `PROMETHEUS_ENABLED`, `PROMETHEUS_ENDPOINT`, and rate-limit variables which map only to `app/config.py`.

## Observability
- `/health` endpoint returns JSON `{"status":"ok"}`.
- `/metrics` exposed at `settings.prometheus.endpoint` with `text/plain` media type.
- Sentry initialized when `SENTRY_DSN` is set; smoke endpoint `/__smoke__/sentry` confirms configuration.

## ML Components
- Prediction pipeline provides numeric-stack fallback in `services/prediction_pipeline.py`.
- Training modules (`app/ml/train_base_glm.py`, `train_modifiers.py`) contain TODOs and unimplemented persistence.
- Retrain scheduler present (`workers/retrain_scheduler.py`) feature-flagged via `RETRAIN_CRON`.

## TODO / FIXME / HACK / WIP / XXX
- app/ml/train_base_glm.py: save model to registry (P1)
- app/handlers.py: replace placeholder with rules implementation (P2)
- telegram/handlers/*: add real statistics (P2)
- scripts/train_model.py: replace hardcoded `season_id` (P2)
- workers/task_manager.py: implement cleanup of old tasks (P1)

## Lint Results
`ruff check app --exclude app/data_processor` → rule I001 (import sorting) triggered in `app/main.py`. Linting of `app/data_processor` fails due to invalid syntax.
