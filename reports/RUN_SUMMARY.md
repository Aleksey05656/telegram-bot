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
- pytest tests/ml/test_glm_training.py -q – pass (1)
- pytest tests/ml/test_modifiers.py -q – pass (1)
- pytest tests/ml/test_bipoisson_sim.py -q – pass (1)

## Modifiers validation
- base_logloss: 1.4236, final_logloss: 1.4236, delta: 0.0000
- base_ece: 0.0147, final_ece: 0.0147, delta: 0.0000
- report: reports/metrics/MODIFIERS_default.md
- gate: OK

## Next Steps
- —
