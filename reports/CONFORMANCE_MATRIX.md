# Conformance Matrix

| Subsystem | Requirement | Implementation | Status | Comment |
| --- | --- | --- | --- | --- |
| Config | Environment-driven settings with .env contract | `config.py`, `app/config.py` | Partial | Two separate settings modules; `.env.example` missing many vars |
| Observability | Sentry init and Prometheus `/metrics` endpoint | `app/observability.py`, `app/main.py` | Partial | Metrics route exists; Sentry optional; duplicate `observability.py` at root |
| API | Basic endpoints `/health`, smoke routes | `app/main.py` | OK | Endpoints implemented |
| Data Processor | Facade for feature engineering and IO | `app/data_processor/*`, `services/data_processor.py` | Partial | Modules exist but invalid header comments break syntax |
| ML | Prediction pipeline, trainers, retrain scheduler | `services/prediction_pipeline.py`, `app/ml/*`, `workers/retrain_scheduler.py` | Partial | Pipelines present but training modules contain TODOs and syntax issues |
| Schedulers/Workers | Retrain registration via env flag | `workers/retrain_scheduler.py`, `workers/runtime_scheduler.py` | OK | Feature flag works in smoke tests |
| CLI/Handlers | CLI entry and bot handlers | `app/cli.py`, `telegram/handlers/*` | Partial | Handlers contain TODO placeholders |
| Tests/CI | Lint and test workflow | `.github/workflows/`, `tests/` | Partial | CI present but tests require external API token and numpy |
