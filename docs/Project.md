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
├─ database/                 | PostgreSQL+Redis, миграции
│  ├─ cache.py
│  ├─ db_logging.py
│  └─ migrations/001_create_predictions.sql
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
└─ requirements.txt
```

## 4. Модель и алгоритмы
### 4.1 Шаг 1 — Базовые λ
Источник: SportMonks (1–2 сезона), признаки xG/xGA, HFA, среднее по лиге.  
Модель: Poisson-GLM (log-link), L2, recency-веса, шринк новичков.  
Выход: λ_base_home, λ_base_away; артефакт модели + `model_info.json`.

### 4.2 Шаг 2 — Динамические модификаторы
Контекст: стадия/мотивация, календарь/усталость, травмы/дисквалификации, ΔxGOT.  
Подход: обучаемый мультипликатор к log(λ_base): `log(λ_final) = log(λ_base) + f(context)` (GLM с оффсетом или GBDT c монотонными ограничениями); каппинг 0.7–1.4.  
Выход: λ_final_home, λ_final_away; фиксация факторов для аудита.

### 4.3 Шаг 3 — Монте-Карло и рынки
≥10k итераций Пуассона по λ_final; при корреляциях — Bi-Variate Poisson/копула.  
Калибровка: Platt/Isotonic; online-контроль ECE/LogLoss.  
Рынки: 1X2, Totals (2.5 + расширение), BTTS, точные счёта (топ-N).  
Value: `fair_odds = 1/p`; сравнение с внешними котировками (если подключено).

## 5. Данные и хранилища
**PostgreSQL / predictions:**  
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
Недельные отчёты.

## 7. Безопасность
Секреты: только ENV/secret-manager. Роли БД: rw и read-only; минимальные привилегии.  
Логи без PII. Rate-limit команд бота. Circuit-breaker API.  
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
