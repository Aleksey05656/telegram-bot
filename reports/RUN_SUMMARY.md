# Run Summary (2025-09-15)

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
- n_sims: 512, rho: 0.1
- entropy: 1x2=1.5798, totals=0.9189, cs=3.7127
- report: reports/metrics/SIM_S_H_vs_A.md
- SQLite: var/predictions.sqlite

## Next Steps
- —
