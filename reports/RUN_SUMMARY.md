# Run Summary (2025-09-15)

## Applied Tasks
- CI staged workflow

## Lint
- make lint-app – warnings (see log)
- make lint – warnings (B034, E402)
- pre-commit – no files to check

## Tests
- pytest – pass (31)
- make smoke – pass
- needs_np – 14 passed, no SKIP

# Run Summary (2025-09-16)

## Applied Tasks
- I1 ENV contract
- I2 Headers to docstrings
- I4 Model registry persistence
- I5 Task manager cleanup

## Lint
- make lint-app – pass
- make lint – pass
- pre-commit-smart – config error (offline)

## Tests
- selected tests – pass (7)
- test_env_contract_required – none

## Smoke
- make smoke – pass

## ENV Contract
- .env.example and app/config.py aligned

# Run Summary (2025-09-15)

## Patches
- 100-config-contract.patch – ALREADY_DONE
- 105-unknown.patch – SKIPPED (file missing)
- 110-observability-metrics.patch – ALREADY_DONE
- 120-ml-skeletons.patch – ROLLED_BACK (numpy AttributeError in tests)
- 130-tests-smoke.patch – APPLIED
- 140-ci-offline-tooling.patch – APPLIED
- 150-data-processor-split.patch – ROLLED_BACK (SportMonks API token required in tests)

## Lint
- make lint-app – pass

## Tests
- tests/test_ml.py – fail (numpy AttributeError)
- tests/smoke/test_endpoints.py – pass
- tests/test_settings.py – pass
- tests/test_services.py – fail (missing API token)
