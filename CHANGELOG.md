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
