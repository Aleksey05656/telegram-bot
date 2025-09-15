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
