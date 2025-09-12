/**
 * @file: ACTION_PLAN.md
 * @description: Roadmap to bring project to production readiness
 * @dependencies: docs/changelog.md, docs/tasktracker.md
 * @created: 2025-09-12
 */

# Action Plan

## Цели релиза
- API и Telegram‑бот запускаются и выдают прогнозы.
- Работает ML‑pipeline с сохранением моделей и метрик.
- Наблюдаемость: `/health`, `/metrics`, Sentry.
- Полный набор тестов и pre-commit в CI.

## Дорожная карта
- **Спринт 0**: устранить конфликты зависимостей, завершить `metrics/metrics.py`, восстановить CI.
- **Спринт 1**: реализовать `services/prediction_pipeline.py`, `workers/retrain_scheduler.py`, убрать TODO в CLI/handlers, декомпозировать `services/data_processor.py`.
- **Спринт 2**: улучшить наблюдаемость, безопасность секретов, расширить тесты и документацию.

## Бэклог задач
| ID | Pri | Компонент | Кратко | Артефакт | Оценка (ч) | Зависимости |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | P0 | deps | синхронизировать версии pandas | обновлённый `requirements.txt`/`constraints.txt` | 2 | – |
| T2 | P0 | services | добавить `prediction_pipeline` | `services/prediction_pipeline.py`, тесты | 8 | T1 |
| T3 | P0 | workers | реализовать `retrain_scheduler` | `workers/retrain_scheduler.py` | 6 | T1 |
| T4 | P1 | metrics | завершить `record_prediction` | рабочий модуль метрик + тест | 4 | T1 |
| T5 | P1 | cli/handlers | убрать TODO, обработка ошибок | обновлённые `app/cli.py`, `telegram/handlers/*` | 5 | – |
| T6 | P1 | data | декомпозировать `services/data_processor.py` | пакет `services/data_processor/*`, тесты | 12 | T1 |
| T7 | P2 | docs | актуализировать `.env.example`, `Project.md` | обновлённая документация | 3 | – |
| T8 | P2 | tests | восстановить тесты и добавить smoke | `tests/`, CI отчёт | 10 | T1 |

## Критический путь и риски
- Версионные конфликты и отсутствие модулей блокируют запуск (меры: пин версий, зеркала PyPI).
- Недоступность внешних API — добавить fallback и smoke‑тесты.
- Тяжёлый `data_processor` — разделение на подмодули и поэтапное покрытие тестами.

## Критерии «готово»
- **API/Telegram**: все команды отвечают, `/health` OK, `/metrics` доступен.
- **ML**: pipeline обучает/сохраняет модель, метрики корректны.
- **Observability**: Sentry события, метрики Prometheus, healthcheck.
- **Config**: все обязательные ENV с валидацией, пример `.env` актуален.
- **Tests/CI**: pre-commit и pytest зелёные, smoke в CI проходит.

