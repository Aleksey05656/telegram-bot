## [2025-09-29] - Build tooling maintenance
### Added
- —

### Changed
- —

### Fixed
- Aligned all mypy pins to 1.7.1 to resolve pip resolution conflicts observed on Amvera builds.

## [2025-10-05] - Value v1.4 audit
### Added
- Multi-provider odds aggregation (`app/lines/aggregator.py`, `app/lines/movement.py`) with weighted consensus and closing line tracking.
- CLV ledger support (`app/value_clv.py`, `database/schema.sql`, migration `20241005_004_value_v1_4.py`) and CLI gate `diagtools/clv_check` with CI job `value-agg-clv-gate` and artefacts `value_clv.{json,md}`.
- Test coverage for aggregation/CLV (`tests/odds/test_aggregator_basic.py`, `tests/odds/test_movement_closing.py`, `tests/value/test_clv_math.py`, `tests/bot/test_portfolio_and_providers.py`, `tests/diag/test_clv_check.py`) plus text fixtures `tests/fixtures/odds_multi/*.csv`.

### Changed
- Bot value workflows now surface consensus lines, movement trends, provider breakdowns and `/portfolio` CLV summary (updates in `app/value_service.py`, `app/bot/formatting.py`, `app/bot/keyboards.py`, `app/bot/routers/{commands,callbacks}.py`).
- Diagnostics extended with Odds Aggregation & CLV sections; `.env.example`, README, docs (`dev_guide`, `user_guide`, `diagnostics`, `Project`, `status/value_v1_4_audit`) and `.github/workflows/ci.yml` reflect new env knobs.

### Fixed
- `diagtools.run_diagnostics` gracefully handles missing `picks_ledger` tables when aggregating CLV metrics.
- CI gate now seeds consensus data before running CLV checks, preventing false negatives when the ledger is empty.

## [2025-10-12] - Diagnostics v2.1 drift packaging
### Added
- `diagtools` package with console scripts `diag-run` and `diag-drift`, reference parquet exports and stratified PSI/KS summaries.
- Drift diagnostics tests covering packaging, stratification, threshold gates and artefact creation.
- CI job `diagnostics-drift` uploading `reports/diagnostics/drift` artefacts and new Prometheus gauges/counters for drift health.

### Changed
- `diagtools.run_diagnostics` aggregates drift statuses, updates metrics and persists enhanced summaries.
- Documentation, README and Makefile updated for `diagtools` entrypoints and new environment variables (`DRIFT_ROLLING_DAYS`, `DRIFT_KS_P_WARN/FAIL`).

### Fixed
- Workflow steps now invoke `python -m diagtools.*` eliminating legacy `tools` imports and sys.path manipulation.

## [2025-09-23] - E6.2: Coverage configuration hardening
### Added
- `.coveragerc` with statement coverage settings omitting migrations, documentation, tests and shell scripts.
- `tools.coverage_enforce` module parsing `coverage.xml`, enforcing thresholds and exporting `reports/coverage_summary.json`.

### Changed
- `Makefile` targets `test-all` and `coverage-html` now emit `coverage.xml`, call the new enforcement tool and render HTML via `coverage html`.
- CI pipeline adds a dedicated `coverage-enforce` step and README documents the new configuration and thresholds.

### Fixed
- Builds fail with exit code 2 when total coverage <80% or workers/database/services/core/services drop below 90% based on `coverage.xml` data.

## [2025-09-22] - E6: CI coverage & reports
### Added
- Deterministic generators `reports/bot_e2e_snapshot.py` and `reports/rc_summary.py` with CI-friendly outputs.
- Coverage enforcement utilities `scripts/coverage_utils.py` and `scripts/enforce_coverage.py` with summary JSON export.
- Makefile targets `test-fast`, `test-smoke`, `test-all`, `coverage-html` for standardized pytest profiles.

### Changed
- GitHub Actions workflow collapsed into staged job (`lint → test-fast → smoke → coverage → reports → artifacts`) with artifact bundle `coverage-and-reports`.
- README documents CI/report flow, coverage thresholds (≥80% total, ≥90% critical packages) and new Makefile commands.

### Fixed
- Coverage now fails build if total or critical package thresholds regress; reports capture version metadata without leaking secrets.

## [2025-09-21] - E5: Amvera deployment pipeline
### Added
- Production-ready multi-stage `Dockerfile`, `.dockerignore` and entrypoint script for Amvera containers.
- `scripts/prestart.py` orchestrating Alembic upgrades plus Postgres/Redis health checks with masked DSN logging.

### Changed
- `Makefile` targets for `docker-build`/`docker-run` tagging images with `APP_VERSION` and `GIT_SHA`.
- `README.md` now documents Amvera deployment flow, required environment and prestart behaviour.

### Fixed
- Exported `mask_dsn()` from `database.db_router` and added `RedisFactory.health_check()` for reliable startup diagnostics.

## [2025-09-20] - E4: Recommendation engine invariants
### Added
- Normalised `RecommendationEngine.generate_prediction` payload and predictor facade in `core/services`.
- Dependency-injected worker with Redis locks and queue status reporting.
- Test suites covering probability invariants and worker behaviour.

### Changed
- README and docs updated with ML invariants and new architecture notes.

### Fixed
- Removed invalid awaits and global clients in prediction worker, resolving audit findings.
