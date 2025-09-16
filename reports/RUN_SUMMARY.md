# Run Summary (2025-09-15)

## data_processor extracted
- pytest --cov=app/data_processor --cov-report=xml --cov-report=html -q — pass (coverage 94.18%, HTML: htmlcov/index.html).

## Applied Tasks
- Очистка конфликтов и обновление зависимостей
- Базовые λ (Poisson-GLM) с валидацией
- Динамические модификаторы
- Монте-Карло и Bi-Poisson

## Lint
- `pip install -r requirements.txt -c constraints.txt --no-index --find-links wheels/` – ResolutionImpossible (scipy)
- `pre-commit run -c .pre-commit-config.offline.yaml --all-files` – first run fixed files, second run passed
- `make lint-app` – formatting applied, reverted
- `make lint` – formatting applied, reverted

## Tests
- pytest tests/ml/test_bipoisson_sim.py -q – pass
- pytest tests/ml/test_calibration_ece.py -q – pass
- pytest tests/storage/test_predictions_store.py -q – pass
- pytest tests/smoke/test_run_simulation_cli.py -q – pass

## CLI retrain
- `scripts/cli.py retrain run` обучает GLM и (опционально) модификаторы, обновляя `LocalModelRegistry` и `reports/RUN_SUMMARY.md`.
- `retrain schedule` регистрирует cron-задачу через in-memory `runtime_scheduler`.
- Smoke-тест `tests/smoke/test_cli_retrain.py` проверяет артефакты и рост `jobs_registered_total`.

## Simulation Integration
- n_sims: 10000, rho: 0.1
- λ_final avg: H=1.3, A=1.3
- entropy: 1x2=1.5737, totals=0.9980, cs=4.1949
- base vs final LogLoss/ECE: 0.0000 / 0.0000
- report: reports/metrics/SIM_default_H_vs_A.md
- SQLite: var/predictions.sqlite

## Next Steps
- —

## CLI retrain
- Season: default
- Data source: synthetic
- GLM artifacts: artifacts/default/glm_home.pkl, artifacts/default/glm_away.pkl
- Model info: artifacts/default/model_info.json
- Modifiers: artifacts/default/modifiers_model.pkl
- Metrics: logloss Δ -0.1756, ece Δ -0.0039
- Metrics report: reports/metrics/MODIFIERS_default.md

## CLI retrain
- Season: default
- Data source: synthetic
- GLM artifacts: artifacts/default/glm_home.pkl, artifacts/default/glm_away.pkl
- Model info: artifacts/default/model_info.json
- Modifiers: artifacts/default/modifiers_model.pkl
- Metrics: logloss Δ -0.1756, ece Δ -0.0039
- Metrics report: reports/metrics/MODIFIERS_default.md

## CLI retrain
- Season: default
- Data source: synthetic
- GLM artifacts: artifacts/default/glm_home.pkl, artifacts/default/glm_away.pkl
- Model info: artifacts/default/model_info.json
- Modifiers: artifacts/default/modifiers_model.pkl
- Metrics: logloss Δ -0.1756, ece Δ -0.0039
- Metrics report: reports/metrics/MODIFIERS_default.md

## CLI retrain
- Season: default
- Data source: synthetic
- GLM artifacts: artifacts/default/glm_home.pkl, artifacts/default/glm_away.pkl
- Model info: artifacts/default/model_info.json
- Modifiers: artifacts/default/modifiers_model.pkl
- Metrics: logloss Δ -0.1756, ece Δ -0.0039
- Metrics report: reports/metrics/MODIFIERS_default.md
