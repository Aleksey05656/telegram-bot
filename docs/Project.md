# Project.md — Документация проекта Telegram-бота для прогнозирования футбольных матчей
*Дата версии:* 2025-08-23
*Ответственный за документ:* Архитектор системы
*Статус:* Актуально

## 1. Назначение и цели
Проект — Telegram-бот, генерирующий вероятностные прогнозы футбольных матчей на основе трёхуровневой модели (базовые λ → динамические модификаторы → Монте-Карло/двумерный Пуассон).
**Цели:**
- Дать калиброванные вероятности рынков (1X2, Totals, BTTS, точные счёта) и value-рекомендации.
- Обеспечить воспроизводимость и аудит: хранить λ_base/λ_final, версии моделей, артефакты и метрики.
- Достичь стабильной онлайновой калибровки (ECE ≤ 0.05 по основным рынкам).

**Не-цели (сейчас):**
- Live in-play поток с секундами латентности.
- Интеграции с букмекерами (только аналитика и рекомендации).

## 2. Стейкхолдеры и роли
- **Владелец продукта**: Маркетолог (приоритеты рынков/лиг, UX).
- **Архитектор/ML-TechLead**: модель, пайплайны, метрики, CI/CD.
- **Разработчики (Python/aiogram/BE)**: сервисы, интеграции, воркеры, БД, кэш.
- **DataOps/DevOps**: окружение, секреты, мониторинг, деплой.
- **Аналитик**: качество, отчёты, калибровка, A/B.

## 3. Обзор архитектуры
```
telegram-bot/
├─ config.py                 | настройки, MODEL_VERSION, env
├─ logger.py                 | логирование (Loguru JSON + Sentry)
├─ observability.py          | инициализация Sentry и Prometheus
├─ core/
│  └─ services/predictor.py      # фасад RecommendationEngine с унифицированным payload
├─ app/
│  ├─ bot/                   | Product v1 Telegram UX (routers, форматирование, кеши, SQLite prefs)
│  │  ├─ caching.py          # TTL LRU-кеш для тяжёлых расчётов
│  │  ├─ formatting.py       # HTML-рендеры (таблицы, explainability)
│  │  ├─ keyboards.py        # inline-кнопки (страницы, детали, экспорт)
│  │  ├─ services.py         # фасад прогнозов + экспорт CSV/PNG
│  │  ├─ storage.py          # schema.sql, user_prefs/subscriptions/reports
│  │  └─ routers/            # commands.py, callbacks.py, state singletons
│  ├─ integrations/
│  │  └─ sportmonks_client.py     # STUB-aware SportMonks API client
│     ├─ validators.py          # Legacy-обёртка на `data_processor.py`
│     ├─ feature_engineering.py # Legacy-обёртка на `data_processor.py`
│     ├─ transformers.py        # Legacy-обёртка на `data_processor.py`
│     └─ io.py                  # Legacy-обёртка на `data_processor.py`
├─ metrics/                  | ECE/LogLoss метрики
│  └─ metrics.py
├─ database/                 | PostgreSQL/SQLite router, Redis, миграции
│  ├─ cache.py
│  ├─ cache_postgres.py
│  ├─ db_logging.py
│  ├─ db_router.py           # Async SQLAlchemy router (read/write, replicas)
│  └─ migrations/
│     ├─ env.py              # Alembic async environment
│     └─ versions/           # Ревизии схемы (predictions и далее)
├─ ml/
│  ├─ base_poisson_glm.py         # Шаг 1: базовые λ
│  ├─ modifiers_model.py          # Шаг 2: динамические модификаторы
│  ├─ montecarlo_simulator.py     # Шаг 3: Монте-Карло / Bi-Poisson
│  ├─ calibration.py              # калибровка (Platt/Isotonic)
├─ services/
│  ├─ data_processor.py           # фичи: xG/xGA, PPDA, усталость, погода
│  ├─ prediction_pipeline.py      # оркестрация трёх уровней
│  ├─ recommendation_engine.py    # fair odds, edge, рекомендации
│  ├─ sportmonks_client.py        # API с ретраями/лимитами
├─ telegram/
│  ├─ bot.py
│  ├─ models.py               | Pydantic модели команд
│  ├─ middlewares.py          | Rate-limit middleware
│  ├─ handlers/ (start, predict, help, terms)
│  └─ utils/formatter.py
├─ workers/
│  ├─ prediction_worker.py        # очередь матчей, апдейты
│  └─ retrain_scheduler.py        # расписание переобучений
├─ scripts/
│  ├─ prepare_datasets.py
│  ├─ train_base_glm.py
│  ├─ train_modifiers.py
│  └─ run_training_pipeline.py
├─ diagtools/
│  ├─ run_diagnostics.py       # агрегированный прогон диагностики
│  ├─ scheduler.py             # CRON/ручной запуск, алерты, логи, метрики
│  ├─ reports_html.py          # генерация HTML-дэшборда и история запусков
│  ├─ drift_ref_update.py      # подготовка drift reference + changelog
│  └─ bench.py / drift/ / golden_regression.py
└─ requirements.txt
```

## 4. Модель и алгоритмы
### 4.1 Шаг 1 — Базовые λ
Реализация: `ml/base_poisson_glm.py`, DI в `RecommendationEngine`.
Источник: SportMonks (1–2 сезона), признаки xG/xGA, HFA, среднее по лиге.
Модель: Poisson-GLM (log-link), L2, recency-веса, шринк новичков.
Выход: λ_base_home, λ_base_away; артефакт модели + `model_info.json`. PredictionPipeline загружает `glm_home.pkl` и `glm_away.pkl` из `LocalModelRegistry`.

### 4.2 Шаг 2 — Динамические модификаторы
Реализация: `ml/modifiers_model.py` (PredictionModifier, CalibrationLayer).
Контекст: стадия/мотивация, календарь/усталость, травмы/дисквалификации, ΔxGOT.
Подход: обучаемый мультипликатор к log(λ_base): `log(λ_final) = log(λ_base) + f(context)` (GLM с оффсетом или GBDT c монотонными ограничениями); каппинг 0.7–1.4.
Выход: λ_final_home, λ_final_away; фиксация факторов для аудита.

### 4.3 Шаг 3 — Монте-Карло и рынки
Реализация: `ml/montecarlo_simulator.py`, калибровка в `ml/calibration.py`.
≥10k итераций Пуассона по λ_final; при корреляциях — Bi-Variate Poisson/копула.
Калибровка: Platt/Isotonic; online-контроль ECE/LogLoss.
Рынки: 1X2, Totals (2.5 + расширение), BTTS, точные счёта (топ-N).
Value: `fair_odds = 1/p`; сравнение с внешними котировками (если подключено).
`RecommendationEngine` нормализует словари 1X2/Totals/BTTS, отбрасывает «грязные» вероятности и сортирует top-k; генерация
детерминирована seed-ом из настроек (`SIM_SEED`).

## 5. Данные и хранилища
**Охват данных:**
- Лиги: Premier League, La Liga, Bundesliga, Serie A, Ligue 1.
- Исторический горизонт: 5 сезонов (с 2018/19).

**PostgreSQL / predictions:**
- Управление пулами и маршрутами чтения/записи реализовано в `database/db_router.py` (автодетект SQLite/Postgres, statement_timeout, health-check).
- Миграции ведутся через Alembic (`database/migrations`, async env + versions).
- fixture_id BIGINT, model_version TEXT, UNIQUE(fixture_id, model_version)
- lambda_base_home/away, lambda_final_home/away NUMERIC(8,4)
- expected_total NUMERIC(8,4) = λ_final_home + λ_final_away (инвариант приложением)
- result_probs, totals_probs, btts_probs, score_probs, recommendations JSONB
- confidence NUMERIC(5,4)
Индексы: fixture_id, model_version; (опц.) по дате матча; партиции по сезону/месяцу.

**Redis (ключи/TTL):**
- `sm:fixture:{id}:raw` — 5–15 мин
- `sm:lineups:{fixture}` — 90–180 сек
- `features:{fixture}:{model}` — до стартового свистка
- `pred:{fixture}:{model}` — до стартового свистка
Инвалидация при апдейтах составов/ключевых новостей; rate-limit/backoff в клиенте.

## 6. Качество, калибровка и мониторинг
Rolling/walk-forward CV; LogLoss, Brier, ECE.
Онлайн-метрики: ECE по декаилям, LogLoss vs baseline, PSI по фичам.
Алёрты: ECE>0.05 или LogLoss↑>15% от референса; PSI>0.25.
Мониторинг: Prometheus (pred_total, prob_bins, rolling_ece, rolling_logloss) и Sentry.
PredictionPipeline дополнительно записывает `glm_base_*` и `glm_mod_final_*`
с тегами `service/env/version/season/modifiers_applied` и формирует
markdown-отчёт `$REPORTS_DIR/metrics/MODIFIERS_<season>.md` (по умолчанию `/data/reports/metrics/...`).
Недельные отчёты.

## 7. Безопасность
Секреты: только ENV/secret-manager. Роли БД: rw и read-only; минимальные привилегии.
Логи без PII. RateLimitMiddleware ограничивает частоту команд бота. Circuit-breaker API.
Валидация входящих данных (pydantic-схемы).

## 8. Производительность и надёжность
p95 ответа бота ≤ 700 мс при кэше; ≤ 3–5 с on-demand прогноз.
Redis-lock per fixture; idempotency (upsert по (fixture_id, model_version)).
Graceful shutdown, health-checks, dead-letter.

## 9. Стандарты разработки
Black, Ruff; mypy(strict); докстринги Google-style.
Pydantic-контракты для JSONB.
Тесты: unit/integration/contract/load; ≥80% в критичных модулях.
Conventional Commits; ветки `feature/*`, `fix/*`, `ml/*`.
CI/CD: линтеры/типы/тесты/миграции → build артефактов (модель, model_info.json) → деплой.

## 10. План разработки (вехи)
M1: базовые λ + сохранение прогнозов (уникальность, expected_total) → внутренний тест.
M2: модификаторы + калибровка, online-ECE → альфа.
M3: value-логика и расширенные рынки → бета.
M4: дашборды и отчётность → прод.

## 11. Консистентность и поддерживаемость
Инварианты: λ≥0; expected_total=λH+λA; JSON-схемы назад-совместимы.
Миграции только вперёд; изменения схемы — через feature-флаги.
Версионирование модели `vYYYY.MM.DD_buildNNN`; логи и БД включают model_version.
Любые изменения архитектуры/требований требуют обновления этого файла и Tasktracker.md.

## 12. Риски и меры
Нехватка/нестабильность данных → кэп модификаторов, штраф в confidence.
Дрифт модели → online-метрики и переобучения по расписанию.
API-лимиты → агрессивный кэш, batch-запросы, ретраи с джиттером.

## 13. Обновление документа
При изменениях: обновить разделы 3–6 и 9, добавить запись в Diary.md и задачи в Tasktracker.md.
