# Run Summary (2025-09-15)

## data_processor extracted
- pytest --cov=app/data_processor --cov-report=term-missing --cov-fail-under=80 -q — pass (coverage 94.18%).

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

## Simulation Integration
- n_sims: 10000, rho: 0.1
- λ_final avg: H=1.3, A=1.3
- entropy: 1x2=1.5737, totals=0.9980, cs=4.1949
- base vs final LogLoss/ECE: 0.0000 / 0.0000
- report: reports/metrics/SIM_default_H_vs_A.md
- SQLite: var/predictions.sqlite

## Next Steps
- —
