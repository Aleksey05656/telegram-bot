# Fix Plan

## Definition of Done
- **API**: `/health`, `/metrics`, and smoke endpoints stable with tests.
- **ML**: Training pipeline saves models; retrain scheduler configurable.
- **Observability**: Single `observability.py`, Sentry DSN optional, metrics exposed.
- **Config**: `.env.example` matches `Settings` definitions.
- **Tests/CI**: `pytest` and `make lint` pass without external tokens; skips documented.
- **Docs**: README and Project.md updated for any new components.

## Roadmap
### Sprint 0 (Blockers)
1. I1 – Sync `.env.example` with `config.py` (P0).
2. I2 – Replace invalid header comments with docstrings (P0).

### Sprint 1 (MVP Docs)
3. I3 – Remove duplicate observability module (P1).
4. I4 – Implement model persistence and parameterization in trainers (P1).

### Sprint 2 (Quality/Observability/Security)
5. I5 – Implement worker cleanup task (P1).
6. I6 – Replace placeholder statistics in handlers (P2).

## Backlog
| ID | P | Component | Summary | Artifact | Est (h) | Depends |
| -- | -- | -------- | ------- | -------- | ------- | ------- |
| I1 | P0 | Config | Sync env vars | patches/100-config-contract.patch | 2 | - |
| I2 | P0 | Syntax | Fix headers to docstrings | patches/150-data-processor-split.patch | 4 | - |
| I3 | P1 | Observability | Consolidate observability module | patches/110-observability-metrics.patch | 3 | I1 |
| I4 | P1 | ML | Save model & parametrize season | patches/120-ml-skeletons.patch | 6 | I1 |
| I5 | P1 | Workers | Implement cleanup | patches/150-data-processor-split.patch | 3 | I2 |
| I6 | P2 | Handlers | Real statistics | patches/130-tests-smoke.patch | 2 | I1 |
