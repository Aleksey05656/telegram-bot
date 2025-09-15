# Issues Register

| ID | Priority | Component | Description | Impact | Location | RCA | Fix Steps | Acceptance | Risks |
| -- | -------- | --------- | ----------- | ------ | -------- | --- | --------- | --------- | ----- |
| I1 | P0 | Config | `.env.example` missing critical vars (`TELEGRAM_BOT_TOKEN`, `SPORTMONKS_API_KEY`, etc.) | Application cannot start or tests fail | `.env.example` vs `config.py` | Docs drift | Align `.env.example` with `config.py` | `python -m pydantic_settings` loads without missing values | Low: requires doc update |
| I2 | P0 | Syntax | Files use `/**` headers causing SyntaxError | Code execution and lint fail | `telegram/middlewares.py:1`, `ml/base_poisson_glm.py:1`, `app/data_processor/__init__.py:1`, etc. | Non-Python comment style | Replace with triple-quoted docstrings | `python -m py_compile` passes | Medium: many files |
| I3 | P1 | Observability | Duplicate `observability.py` modules; unclear which is used | Confusion, potential misconfig | `observability.py`, `app/observability.py` | Historical leftovers | Remove root module; ensure single implementation | Smoke tests still pass | Low |
| I4 | P1 | ML | Training modules contain TODOs (save model, hardcoded season id) | Model artifacts not persisted, retrain unsafe | `app/ml/train_base_glm.py:31`, `scripts/train_model.py:728` | Incomplete implementation | Implement persistence and parameterization | Tests for training save artifacts | Medium |
| I5 | P1 | Workers | Cleanup task unimplemented | Old tasks accumulate | `workers/task_manager.py:520` | Not yet implemented | Implement cleanup logic | Smoke test for cleanup passes | Low |
| I6 | P2 | Handlers | Placeholder statistics in bot handlers | Users see stub data | `telegram/handlers/start.py:214`, `telegram/handlers/help.py:63` | Feature not implemented | Fetch and display real stats | Bot commands return real stats | Low |
