<!--
@file: ARCHITECTURE.md
@description: Current architecture overview
@dependencies: docs/Project.md
@created: 2025-09-10
-->

# Architecture

Updated 2025-09-10.

- **app/** – FastAPI application with configuration, middlewares and observability.
- **services/** – business logic and data processing utilities.
- **ml/** – machine learning models и `LocalModelRegistry` (артефакты в каталоге `artifacts/` или `MODEL_REGISTRY_PATH`) и prediction pipeline.
- **tests/** – unit, contract, smoke and end-to-end tests.
- SportMonks client (`app/integrations/sportmonks_client.py`) переключает заглушку через `SPORTMONKS_STUB`.

## ML stack

Core libs: numpy >=1.26,<2.0 and pandas 2.2.2.

See `docs/Project.md` for a detailed design.
