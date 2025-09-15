# Run Summary (2025-09-15)

## Applied Tasks
- Ruff warnings cleanup

## Lint
- pre-commit (offline) – OK (ruff-check, black, isort, trailing-whitespace, end-of-file-fixer)
- make lint-app – pass
- make lint – pass

## Tests
- pytest -q – pass (31)
- pytest -q -m needs_np – pass (14)
- make smoke – pass (8)
  - /health → 200
  - /metrics → 200 text/plain
  - /__smoke__/retrain.jobs_registered_total → 0.0

## Ruff Leftovers
- none

## Next Steps
- —
