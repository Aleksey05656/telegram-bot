## Dev Guide: Product v1 Bot Architecture

### Пакет `app.bot`
- `caching.py` — асинхронный TTL-кеш с LRU-эвикцией и счётчиками hit/miss.
- `formatting.py` — HTML-рендеры для всех команд (таблицы, объяснимость, дайджесты, consensus-блоки и сводка портфеля).
- `keyboards.py` — генерация inline-клавиатур (пагинация, детали матча, экспорт, кнопки «Провайдеры» и «Почему {provider}» для value-карточек).
- `services.py` — фасад прогнозов: интеграция с SportMonks, вычисление fair-odds, модификаторов, генерация CSV/PNG.
- `storage.py` — SQLite-схема и операции (`user_prefs`, `subscriptions`, `reports`).
- `routers/commands.py` — обработчики aiogram-команд с кешированием, пагинацией, логированием и записью value-портфеля (`/portfolio`).
- `routers/callbacks.py` — обработка inline callback для перелистывания, карточек матча, экспорта и расшифровки провайдеров (включая объяснение best-price маршрута по кнопке «Почему …»).
- `state.py` — singletons для кешей и PredictionFacade.

### Поток `/today`
1. Парсинг аргументов (`league`, `limit`, `user_id`).
2. Получение прогнозов через `PredictionFacade.today`; результаты кешируются на `CACHE_TTL_SECONDS`.
3. Форматирование ответа (`format_today_matches`) и построение клавиатуры `today_keyboard`.
4. Состояние пагинации сохраняется в `PAGINATION_CACHE` (ключ — хэш запроса).
5. Callback `page:*` достаёт срез из кеша и редактирует сообщение без повторного расчёта.

### Explainability & Export
- `PredictionFacade._build_modifiers` формирует три ключевых фактора (мотивация, усталость, травмы) и дельты вероятностей.
- `/explain` и callback `explain:*` используют общий кеш `MATCH_CACHE`, чтобы не дергать API повторно.
- `generate_csv` и `generate_png` создают артефакты в `REPORTS_DIR`, записи логируются в таблицу `reports`.

### SQLite Schema
- `user_prefs`: хранит язык, часовой пояс, формат коэффициентов.
- `subscriptions`: уникальный `user_id`, время рассылки, опциональная лига.
- `reports`: история экспортов с путём к файлу.
- Миграция применяется автоматически при первом обращении (`ensure_schema`).
- `value_alerts`: фича-флаг value-уведомлений (enabled, edge_threshold, league).
- `value_alerts_sent`: история отправленных алертов (user_id, match_key, market, selection, sent_at, edge_pct).
- `value_calibration`: результаты калибровки порогов per лига/рынок (`tau_edge`, `gamma_conf`, `samples`, `metric`, `updated_at`).
- `odds_snapshots`: снимки котировок (поставщик, матч, рынок, выбор, цена, JSON `extra`). Идемпотентный upsert по `(provider, match_key, market, selection)`.
- `closing_lines`: последний консенсусный коэффициент перед стартом (уникальный индекс по `(match_key, market, selection)`).
- `picks_ledger`: журнал value-сигналов с коэффициентами (market/provider/consensus/closing), CLV и ROI (индексы `picks_ledger_user_idx`, `picks_ledger_match_idx`).
- `provider_stats`: агрегаты надёжности провайдеров (samples, fresh_success/fail, latency, z-стабильность, closing bias, score) для best-price роутинга и диагностики.
- Индекс `odds_snapshots_match_time` по `(match_key, market, selection, pulled_at_utc)` ускоряет выборку последних котировок для best-price маршрута.

### Метрики и логирование
- `bot_commands_total{cmd}` — все команды и callbacks (`export_callback`).
- `bot_digest_sent_total` — счётчик ежедневных дайджестов (подключается в планировщике).
- `render_latency_seconds{cmd}` — гистограмма времени форматирования (команды и callbacks).
- Логгер добавляет `user_id`, `cmd`, `cache_hit` и аргументы для ключевых команд.
- Value-метрики (`app.metrics`): `value_candidates_total`, `value_picks_total`, `value_detector_latency_seconds`, `value_confidence_avg`, `value_edge_weighted_avg`, `value_backtest_last_run_ts`, `value_backtest_sharpe{league,market}`, `value_backtest_samples{league,market}`, `value_calibrated_pairs_total`.
- Надёжность/сеттлмент: `provider_reliability_score`, `provider_fresh_share`, `provider_latency_ms`, `odds_anomaly_detected_total`, `picks_settled_total{outcome}`, `portfolio_roi_rolling{window_days}`, `clv_mean_pct`.

### ENV и конфиг
- `PAGINATION_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `ADMIN_IDS`, `DIGEST_DEFAULT_TIME` — новые параметры в `config.Settings`.
- `matplotlib>=3.8` добавлена в зависимости для экспорта PNG.
- `database/schema.sql` содержит `PRAGMA user_version = 1` и DDL таблиц.
- Value/odds параметры (`ODDS_PROVIDERS`, `ODDS_PROVIDER_WEIGHTS`, `ODDS_PROVIDER`, `ODDS_AGG_METHOD`, `ODDS_TIMEOUT_SEC`, `RELIABILITY_*`, `RELIAB_V2_ENABLE`, `RELIAB_DECAY`, `RELIAB_MIN_SAMPLES`, `RELIAB_SCOPE`, `RELIAB_COMPONENT_WEIGHTS`, `RELIAB_PRIOR_*`, `RELIAB_STAB_Z_TOL`, `RELIAB_CLOSING_TOL_PCT`, `ANOMALY_Z_MAX`, `BEST_PRICE_*`, `VALUE_MIN_EDGE_PCT`, `VALUE_CONFIDENCE_METHOD`, `VALUE_ALERT_COOLDOWN_MIN`, `VALUE_ALERT_QUIET_HOURS`, `VALUE_ALERT_MIN_EDGE_DELTA`, `VALUE_STALENESS_FAIL_MIN`, `BACKTEST_*`, `GATES_VALUE_SHARPE_*`, `CLV_FAIL_THRESHOLD_PCT`, `SETTLEMENT_*`, `PORTFOLIO_ROLLING_DAYS`, `ENABLE_VALUE_FEATURES` и т.д.) добавлены в `config.py` и `.env.example`.
- `ODDS_FIXTURES_PATH` — вспомогательная переменная окружения для CSV-фикстур в оффлайн-тестах.

### Тесты
- `tests/bot/` покрывает форматирование, клавиатуры, кеш, экспорт, SQLite (включая `/portfolio` и блок «Провайдеры»).
- `test_env_contract.py` гарантирует актуальность `.env.example`.
- Для асинхронных тестов используется `pytest.mark.asyncio`.
- `tests/odds/` — модульные тесты для overround, CSV-провайдера и мультипровайдерного агрегатора (best/median/weighted, closing line).
- `tests/diag/test_value_check.py` — проверяет CLI `diagtools.value_check` (корректный exit code и наличие котировок).
- `tests/diag/test_clv_check.py` — проверяет CLI `diagtools.clv_check` (артефакты и exit-коды 0/1/2).
- `tests/odds/test_reliability.py`, `tests/odds/test_reliability_v2_bayes.py`, `tests/odds/test_best_route.py`, `tests/odds/test_aggregator_weighted_scores.py`, `tests/odds/test_anomaly_filter.py` — проверяют скоринг провайдеров, байесовский скоринг/декея, best-price роутинг и фильтр аномалий.
- `tests/value/test_settlement_engine.py` — сеттлмент рынков 1X2/OU/BTTS и расчёт ROI.
- `tests/bot/test_portfolio_extended.py` — расширенный рендер `/portfolio` и блок «Best price».
- `tests/diag/test_provider_quality.py`, `tests/diag/test_provider_quality_gate.py`, `tests/diag/test_settlement_check.py` — гейты качества провайдеров, Bayesian reliability и сеттлмента.
- `tests/bot/test_value_commands.py` — сценарии `/value`, `/compare`, `/alerts`.
- `tests/value/` — backtest окна, подбор порогов, вес `edge_w`, антиспам алертов, рендер объяснений и вычисление CLV в `picks_ledger`.

#### Offline QA
- CI job `offline-qa` устанавливает только `pytest` и прогоняет `pytest -q` с `USE_OFFLINE_STUBS=1`, чтобы убедиться: база кода импортируется и запускается без `numpy`, `pandas`, `sqlalchemy`, `joblib` и других тяжёлых колёс.
- В `tests/_stubs/` лежат лёгкие модули-заменители; `tests/conftest.py` подключает их, если реальные зависимости недоступны, а также принудительно при установленной переменной `USE_OFFLINE_STUBS`.
- Тесты, помеченные `needs_np`, автоматически помечаются `skip`, если проверка `_numpy_stack_ok` не прошла (например, когда задействованы стабы).
- Чтобы вернуться к реальным библиотекам, установите зависимости и сбросьте `USE_OFFLINE_STUBS`.

### Поставщики котировок и нормализация
- Пакет `app.lines` содержит:
  - `providers.base` — интерфейс `LinesProvider` и `OddsSnapshot` (normalised строки).
  - `providers.csv` — оффлайн-провайдер из CSV-файлов (`fixtures_dir`), нормализует колонки и timestamp.
  - `providers.http` — HTTP-клиент с `httpx.AsyncClient`, ETag-кешем и rate limit (token bucket).
  - `mapper` — преобразование `home/away/league/kickoff` в `match_key` на основе `app.mapping.keys`.
  - `storage.OddsSQLiteStore` — хранение последних котировок в SQLite (upsert + индексы `odds_match`, `odds_match_time`).
  - `reliability` — EMA-скоринг покрытия/свежести/лагов/стабильности, сохранение в `provider_stats`, метрики Prometheus (legacy).
  - `reliability_v2` — Bayesian-скоринг с экспоненциальным забыванием (Beta свежесть, Gamma латентность, z-стабильность, closing bias), Prometheus-метрики по компонентам и итоговому score.
  - `anomaly` — фильтрация выбросов по z-score/квантилям и счётчик `odds_anomaly_detected_total`.
  - `aggregator` — консенсус (best/median/weighted), тренды closing line, best-price роутинг (`pick_best_route`).
  - `movement` — определение тренда и closing line в окне `CLV_WINDOW_BEFORE_KICKOFF_MIN`.
- Overround-нормализация (`app/pricing/overround.py`):
  - `decimal_to_probabilities` → implied `p`.
  - `normalize_market(..., method="proportional"|"shin")` — приводим сумму вероятностей к 1; Shin доступен для 1X2.
  - `probabilities_to_decimal` — обратное преобразование (`fair price`).

### Value-детектор и сервис
- `app/value_detector.ValueDetector` вычисляет edge = `(fair/market_price - 1) * 100`, преобразует уверенность `confidence`: при `VALUE_CONFIDENCE_METHOD=mc_var` используется `conf = 1 / (1 + variance)` из дисперсии Монте-Карло. Взвешенный edge `edge_w = edge * conf` участвует в сортировке; калиброванные пороги (`tau_edge`, `gamma_conf`) подтягиваются через `CalibrationService`.
- `app/value_calibration` содержит `BacktestRunner` (валидация `time_kfold`|`walk_forward`, оптимизация `BACKTEST_OPTIM_TARGET`) и `CalibrationService`, который хранит результаты в SQLite (`value_calibration`).
- `app/value_alerts.AlertHygiene` применяет антиспам-правила: cooldown (`VALUE_ALERT_COOLDOWN_MIN`), quiet hours (`VALUE_ALERT_QUIET_HOURS`), минимальную дельту (`VALUE_ALERT_MIN_EDGE_DELTA`), контроль ста́лости (`VALUE_STALENESS_FAIL_MIN`). Отправки логируются в `value_alerts_sent`.
- `app/value_clv.PicksLedgerStore` сохраняет value-сигналы, записывает `provider_price_decimal` и `consensus_price_decimal`, вычисляет CLV (`calculate_clv`) и обновляет closing line (`closing_lines`).
- `app/value_service.ValueService` объединяет `PredictionFacade` и мультипровайдер `LinesProvider`, формирует карточки (`value_picks`) и сравнительные отчёты (`compare`) с consensus-линией, блоком best-price и пояснениями edge.
- `app/settlement/engine.py` подтягивает финальные счета SportMonks, сеттлит рынки 1X2/OU/BTTS, рассчитывает ROI/CLV и обновляет rolling-метрики портфеля.
- Команды бота `/value`, `/compare`, `/alerts` используют `ValueService`, выводят `τ/γ`, `edge_w`, историю алертов и сохраняют настройки в `value_alerts` и `value_alerts_sent`.
- CLI `diagtools.value_check` проверяет провайдера котировок и запускает калибровку (опции `--calibrate`, `--days`). Отчёты сохраняются в `reports/diagnostics/value_calibration.{json,md}` и учитывают гейты `GATES_VALUE_SHARPE_*` и `BACKTEST_MIN_SAMPLES`.
- CLI `diagtools.clv_check` агрегирует `picks_ledger` (средний CLV, доля положительных записей) и формирует `reports/diagnostics/value_clv.{json,md}`; exit-коды используются CI job `value-agg-clv-gate`.
- CLI `diagtools.provider_quality` публикует `{json,md}`-сводки по Bayesian-скорингу провайдеров (score, coverage, latency, WARN/FAIL статусы) и используется в CI job `reliability-v2-gate`/`value-agg-clv-gate`; `diagtools.settlement_check` — ROI-гейт по сеттлменту.
