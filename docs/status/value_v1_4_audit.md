"""
/**
 * @file: docs/status/value_v1_4_audit.md
 * @description: Value v1.4 audit summary (modules, schema, diagnostics, commands).
 * @dependencies: docs/diagnostics.md, docs/dev_guide.md, docs/Project.md
 * @created: 2025-10-05
 */
"""

# Value v1.4 Audit — Summary

## Модули и интеграции
- `app/lines/aggregator.py` — best/median/weighted консенсус, веса `ODDS_PROVIDER_WEIGHTS`, история в SQLite.
- `app/lines/movement.py` — окно `CLV_WINDOW_BEFORE_KICKOFF_MIN`, тренды ↗︎/↘︎/→, closing line.
- `app/value_clv.py` — расчёт CLV, запись в `picks_ledger`, обновление `closing_lines`, агрегация портфеля.
- `app/value_service.py`, `app/bot/formatting.py`, `app/bot/keyboards.py`, `app/bot/routers/{commands,callbacks}.py` выводят consensus, тренды, кнопку «Провайдеры» и `/portfolio`.

## Схема и индексы
- Alembic `20241005_004_value_v1_4` и `database/schema.sql` создают `closing_lines`, `picks_ledger`, индекс `idx_odds_snapshots_match_time`, уникальные ключи `uq_closing_lines`, `uq_picks_ledger_entry`, индексы `picks_ledger_{user,match}_idx`.
- SQLite guard `tools/ci_assert_no_binaries.sh` остаётся первым шагом.

## Диагностика и CI
- `diagtools.run_diagnostics` расширен секциями «Odds Aggregation» и «CLV».
- CLI `diagtools.clv_check` формирует `reports/diagnostics/value_clv.{json,md}` и гейт `value-agg-clv-gate`.
- CI workflow добавляет job `value-agg-clv-gate`; артефакты: `reports/diagnostics/value_calibration.*`, `reports/diagnostics/value_clv.*`.

## Команды и CLI
- Ботовые карточки `/value` и `/compare` включают «Consensus X.XX (n=Y) [↗︎/↘︎/→]» и кнопку «Провайдеры».
- `/portfolio` показывает `avg_clv`, долю положительных CLV, количество записей.
- CLI проверки: `python -m diagtools.value_check --calibrate`, `python -m diagtools.clv_check --db-path $DB_PATH --reports-dir $REPORTS_DIR/diagnostics`.

## Покрытие тестами
- `tests/odds/test_aggregator_basic.py`, `tests/odds/test_movement_closing.py` — консенсус, closing line.
- `tests/value/test_clv_math.py` — формула CLV + запись в `picks_ledger`.
- `tests/bot/test_portfolio_and_providers.py` — рендер карточек, кнопка «Провайдеры», сводка портфеля.
- `tests/diag/test_clv_check.py` — артефакты и exit-коды CLI `clv_check`.

*Статус: аудит Value v1.4 завершён, функциональность подтверждена тестами и документацией.*
