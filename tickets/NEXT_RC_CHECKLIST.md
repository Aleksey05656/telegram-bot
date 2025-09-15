/**
 * @file: tickets/NEXT_RC_CHECKLIST.md
 * @description: Pending tasks before next release candidate
 * @dependencies: docs/tasktracker.md
 * @created: 2025-09-15
 */

# Next RC Checklist

1. Generate `requirements.lock` with hashes – High – 2h
2. Introduce `SENTRY_ENABLED` toggle in settings and `.env.example` – High – 1h
3. Add `service` and `version` labels to `/metrics` – Medium – 1h
4. Expose `jobs_registered_total` in `workers/runtime_scheduler` and `__smoke__/retrain` – Medium – 2h
5. Implement numeric e2e test for model save/load/predict_proba marked `@needs_np` – High – 3h
6. Document "Local wheels" and "CI numeric enforcement" sections in README and ARCHITECTURE – Medium – 2h
