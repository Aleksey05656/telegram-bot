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
- **ml/** – machine learning models, `LocalModelRegistry` and prediction pipeline.
- **tests/** – unit, contract, smoke and end-to-end tests.

See `docs/Project.md` for a detailed design.
