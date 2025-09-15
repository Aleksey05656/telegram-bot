| Patch | Status | Files/Remap | Comment |
|-------|--------|-------------|---------|
|100-config-contract|ALREADY_DONE|.env.example, app/config.py|env variables and aliases already present|
|105-? |SKIPPED|-|patch file missing|
|110-observability-metrics|ALREADY_DONE|app/observability.py, tests/smoke/test_metrics_endpoint.py|metrics endpoint and smoke test already exist|
|120-ml-skeletons|ADAPTED|ml/*.py|converted C-style headers to docstrings|
|130-tests-smoke|ADAPTED|tests/smoke/test_endpoints.py|add smoke tests for core endpoints|
|140-ci-offline-tooling|ADAPTED|.github/workflows/ci.yml|use make pre-commit-smart for offline linting|
|150-data-processor-split|ADAPTED|data_processor.py -> app/data_processor/*|replace monolithic utilities with facade|

No manual follow-ups required.
