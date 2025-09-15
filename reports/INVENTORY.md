# Repository Inventory

## Documentation
- ARCHITECTURE.md
- AUDIT_REPORT.md
- DEBT_CHECKLIST.md
- README.md
- docs/Diary.md
- docs/Project.md
- docs/changelog.md
- docs/qa.md
- docs/tasktracker.md

## Directory Tree (depth 3)
```
.
./.git
./.git/branches
./.git/hooks
./.git/info
./.git/logs
./.git/logs/refs
./.git/objects
./.git/objects/3d
./.git/objects/65
./.git/objects/96
./.git/objects/c3
./.git/objects/d5
./.git/objects/f3
./.git/objects/f9
./.git/objects/info
./.git/objects/pack
./.git/refs
./.git/refs/heads
./.git/refs/remotes
./.git/refs/tags
./.github
./.github/workflows
./app
./app/data_processor
./app/ml
./database
./database/migrations
./docs
./metrics
./ml
./ml/models
./patches
./reports
./scripts
./scripts/hooks
./services
./telegram
./telegram/handlers
./telegram/utils
./tests
./tests/contracts
./tests/integration
./tests/smoke
./workers
```

## Modules
### app/
```
app/__init__.py
app/cli.py
app/config.py
app/data_processor/__init__.py
app/data_processor/feature_engineering.py
app/data_processor/io.py
app/data_processor/transformers.py
app/data_processor/validators.py
app/handlers.py
app/main.py
app/middlewares.py
app/ml/__init__.py
app/ml/prediction_pipeline.py
app/ml/retrain_scheduler.py
app/ml/train_base_glm.py
app/ml/train_modifiers.py
app/observability.py
```

### services/
```
services/__init__.py
services/data_processor.py
services/prediction_pipeline.py
services/recommendation_engine.py
services/sportmonks_client.py
```

### workers/
```
workers/__init__.py
workers/prediction_worker.py
workers/retrain_scheduler.py
workers/runtime_scheduler.py
workers/task_manager.py
```

### tests/
```
tests/conftest.py
tests/contracts/__init__.py
tests/contracts/test_settings_contract.py
tests/integration/__init__.py
tests/integration/test_end_to_end.py
tests/smoke/test_retrain_registration.py
tests/test_metrics.py
tests/test_metrics_sentry.py
tests/test_ml.py
tests/test_pipeline_stub.py
tests/test_services.py
tests/test_services_workers_minimal.py
tests/test_settings.py
tests/test_todo_barriers.py
```

## TODO / FIXME / HACK / WIP / XXX markers
```
app/ml/train_base_glm.py-29-    """
app/ml/train_base_glm.py-30-    model = DummyModel()
app/ml/train_base_glm.py:31:    # TODO: сохранить модель в реестр (локально/S3). Пока возвращаем.
app/ml/train_base_glm.py-32-    return model
--
app/handlers.py-13-
app/handlers.py-14-    # Временная заглушка, чтобы поведение было детерминированным
app/handlers.py:15:    # вместо «тихого» TODO
app/handlers.py-16-    return {"status": "ok", "note": "rules are not implemented yet"}
--
telegram/handlers/start.py-212-    try:
telegram/handlers/start.py-213-        logger.debug(f"Пользователь {callback.from_user.id} запросил статистику")
telegram/handlers/start.py:214:        # TODO: Добавить реальную статистику
telegram/handlers/start.py-215-        stats_text = (
telegram/handlers/start.py-216-            "📊 <b>Статистика Football Predictor Bot</b>\n\n"
--
telegram/handlers/help.py-61-            ).strip()
telegram/handlers/help.py-62-        elif command == "stats":
telegram/handlers/help.py:63:            # TODO: Добавить реальную статистику
telegram/handlers/help.py-64-            help_text = textwrap.dedent(
telegram/handlers/help.py-65-                """
--
telegram/handlers/help.py-191-            f"Пользователь {callback.from_user.id} запросил статистику через callback"
telegram/handlers/help.py-192-        )
telegram/handlers/help.py:193:        # TODO: Добавить реальную статистику
telegram/handlers/help.py-194-        stats_text = textwrap.dedent(
telegram/handlers/help.py-195-            """
--
scripts/train_model.py-726-    """Внутренняя асинхронная функция для выполнения логики переобучения."""
scripts/train_model.py-727-    # Получаем данные для обучения
scripts/train_model.py:728:    # TODO: Замените season_id на актуальный ID сезона или используйте значение по умолчанию
scripts/train_model.py-729-    if season_id is None:
scripts/train_model.py-730-        season_id = 23855  # Пример: Premier League 2023/2024 (замените на актуальный)
--
scripts/train_model.py-744-        logger.info("🚀 Запуск скрипта обучения Poisson-регрессионной модели")
scripts/train_model.py-745-        # Получаем данные для обучения
scripts/train_model.py:746:        # TODO: Замените season_id на актуальный ID сезона
scripts/train_model.py-747-        season_id = 23855  # Пример: Premier League 2023/2024
scripts/train_model.py-748-        training_data = await fetch_training_data(season_id=season_id)
--
README-200-------------------------------------------------------------------------
README-201-
README:202:## TODO / Roadmap
README-203-
README-204--   [ ] Поддержка live-in-play прогнозов\
--
workers/task_manager.py-518-        print(json.dumps(stats, indent=2, ensure_ascii=False))
workers/task_manager.py-519-    elif args.action == "cleanup":
workers/task_manager.py:520:        # TODO: Реализовать очистку старых задач
workers/task_manager.py-521-        print("Очистка задач еще не реализована")
workers/task_manager.py-522-    elif args.action == "failed":
```

## Configuration and Tooling
- pyproject.toml
- requirements.txt
- constraints.txt
- ruff.toml
- pytest.ini
- mypy.ini
- pip.conf
- .env.example
- .github/workflows/
- docker-compose.yml
- Makefile
- scripts/
