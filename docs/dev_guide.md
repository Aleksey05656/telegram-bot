## Dev Guide: Product v1 Bot Architecture

### Пакет `app.bot`
- `caching.py` — асинхронный TTL-кеш с LRU-эвикцией и счётчиками hit/miss.
- `formatting.py` — HTML-рендеры для всех команд (таблицы, объяснимость, дайджесты).
- `keyboards.py` — генерация inline-клавиатур (пагинация, детали матча, экспорт).
- `services.py` — фасад прогнозов: интеграция с SportMonks, вычисление fair-odds, модификаторов, генерация CSV/PNG.
- `storage.py` — SQLite-схема и операции (`user_prefs`, `subscriptions`, `reports`).
- `routers/commands.py` — обработчики aiogram-команд с кешированием, пагинацией и логированием.
- `routers/callbacks.py` — обработка inline callback для перелистывания, карточек матча, экспорта.
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
- `odds_snapshots`: снимки котировок (поставщик, матч, рынок, выбор, цена, JSON `extra`). Идемпотентный upsert по `(provider, match_key, market, selection)`.

### Метрики и логирование
- `bot_commands_total{cmd}` — все команды и callbacks (`export_callback`).
- `bot_digest_sent_total` — счётчик ежедневных дайджестов (подключается в планировщике).
- `render_latency_seconds{cmd}` — гистограмма времени форматирования (команды и callbacks).
- Логгер добавляет `user_id`, `cmd`, `cache_hit` и аргументы для ключевых команд.
- Value-метрики (`app.metrics`): `value_candidates_total`, `value_picks_total`, `value_detector_latency_seconds`.

### ENV и конфиг
- `PAGINATION_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `ADMIN_IDS`, `DIGEST_DEFAULT_TIME` — новые параметры в `config.Settings`.
- `matplotlib>=3.8` добавлена в зависимости для экспорта PNG.
- `database/schema.sql` содержит `PRAGMA user_version = 1` и DDL таблиц.
- Value/odds параметры (`ODDS_PROVIDER`, `ODDS_TIMEOUT_SEC`, `VALUE_MIN_EDGE_PCT`, `ENABLE_VALUE_FEATURES` и т.д.) добавлены в `config.py` и `.env.example`.
- `ODDS_FIXTURES_PATH` — вспомогательная переменная окружения для CSV-фикстур в оффлайн-тестах.

### Тесты
- `tests/bot/` покрывает форматирование, клавиатуры, кеш, экспорт, SQLite.
- `test_env_contract.py` гарантирует актуальность `.env.example`.
- Для асинхронных тестов используется `pytest.mark.asyncio`.
- `tests/odds/` — модульные тесты для overround и CSV-провайдера котировок.
- `tests/diag/test_value_check.py` — проверяет CLI `diagtools.value_check` (корректный exit code и наличие котировок).
- `tests/bot/test_value_commands.py` — сценарии `/value`, `/compare`, `/alerts`.

### Поставщики котировок и нормализация
- Пакет `app.lines` содержит:
  - `providers.base` — интерфейс `LinesProvider` и `OddsSnapshot` (normalised строки).
  - `providers.csv` — оффлайн-провайдер из CSV-файлов (`fixtures_dir`), нормализует колонки и timestamp.
  - `providers.http` — HTTP-клиент с `httpx.AsyncClient`, ETag-кешем и rate limit (token bucket).
  - `mapper` — преобразование `home/away/league/kickoff` в `match_key` на основе `app.mapping.keys`.
  - `storage.OddsSQLiteStore` — хранение последних котировок в SQLite (upsert + индекс `odds_match`).
- Overround-нормализация (`app/pricing/overround.py`):
  - `decimal_to_probabilities` → implied `p`.
  - `normalize_market(..., method="proportional"|"shin")` — приводим сумму вероятностей к 1; Shin доступен для 1X2.
  - `probabilities_to_decimal` — обратное преобразование (`fair price`).

### Value-детектор и сервис
- `app/value_detector.ValueDetector` фильтрует и сортирует value-кейсы: edge = `(fair/market_price - 1) * 100`, фильтры по `min_edge_pct`, `min_confidence`, `markets`, лимит `max_picks`.
- `app/value_service.ValueService` объединяет `PredictionFacade` и `LinesProvider`, строит `ModelOutcome`, выдаёт карточки (`value_picks`) и сравнительные отчёты (`compare`).
- Команды бота `/value`, `/compare`, `/alerts` используют `ValueService` и сохраняют пользовательские настройки в `value_alerts`.
- CLI `diagtools.value_check` под флагом CI проверяет провайдера котировок: читает прогнозы, загружает рынки, возвращает `SystemExit(1)` при отсутствии котировок или невалидных значениях.
