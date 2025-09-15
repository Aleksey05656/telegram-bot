# Dynamic Checks

## Lint
Command: `make lint-app`
Result: `Found 1 error (1 fixed, 0 remaining). All checks passed.`
Top rule: import sorting (I001) in `app/main.py`

## Tests
Command: `pytest -q`
Result: 3 failed, 14 passed
Top failures:
- `tests/test_ml.py::test_outcome_probabilities_sum_to_one` – `AttributeError: module 'numpy' has no attribute 'math'`
- `tests/test_services.py::test_compute_rest_days` – `ValueError: API token for SportMonks is required`
- `tests/test_services.py::test_haversine_km` – `ValueError: API token for SportMonks is required`

## Smoke (FastAPI TestClient)
- `/health` → 200 `application/json`
- `/metrics` → 200 `text/plain`
- `/__smoke__/sentry` → 200, `{"sent":false,"reason":"dsn not configured"}`
- `/__smoke__/retrain` → 200, retrain disabled
