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
