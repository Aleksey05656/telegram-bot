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

### Метрики и логирование
- `bot_commands_total{cmd}` — все команды и callbacks (`export_callback`).
- `bot_digest_sent_total` — счётчик ежедневных дайджестов (подключается в планировщике).
- `render_latency_seconds{cmd}` — гистограмма времени форматирования (команды и callbacks).
- Логгер добавляет `user_id`, `cmd`, `cache_hit` и аргументы для ключевых команд.

### ENV и конфиг
- `PAGINATION_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `ADMIN_IDS`, `DIGEST_DEFAULT_TIME` — новые параметры в `config.Settings`.
- `matplotlib>=3.8` добавлена в зависимости для экспорта PNG.
- `database/schema.sql` содержит `PRAGMA user_version = 1` и DDL таблиц.

### Тесты
- `tests/bot/` покрывает форматирование, клавиатуры, кеш, экспорт, SQLite.
- `test_env_contract.py` гарантирует актуальность `.env.example`.
- Для асинхронных тестов используется `pytest.mark.asyncio`.
