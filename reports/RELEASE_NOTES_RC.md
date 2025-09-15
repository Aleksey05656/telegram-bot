<!--
@file: RELEASE_NOTES_RC.md
@description: Release candidate notes
@dependencies: docs/changelog.md, reports/RUN_SUMMARY.md
@created: 2025-09-15
-->

# Release Candidate v1.0.0-rc1

## Highlights
- GLM base λ with modifiers
- Bi-Poisson simulator and entropy metrics
- Storage via SQLite predictions store
- Observability with Sentry toggle and Prometheus labels

## Metrics snapshot
- n_sims: 10000, rho: 0.1
- λ_final avg: H=1.3, A=1.3
- entropy: 1x2=1.5737, totals=0.9980, cs=4.1949
- base vs final LogLoss/ECE: 0.0000 / 0.0000

## Artifacts
- reports/metrics/SIM_default_H_vs_A.md
- reports/metrics/ECE_simulation_default_H_vs_A.md
- var/predictions.sqlite

## Ops
- Tune SIM_RHO, SIM_N, SIM_CHUNK via environment variables
- Disable Sentry with `SENTRY__ENABLED=false`
- Toggle SportMonks stub via `SPORTMONKS_STUB`

Tag: v1.0.0-rc1
