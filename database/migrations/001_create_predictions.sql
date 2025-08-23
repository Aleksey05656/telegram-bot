-- database/migrations/001_create_predictions.sql
-- Хранилище прогнозов и результатов для бэктестинга и аналитики
-- Проект: Telegram-бот спортивных прогнозов (PostgreSQL)
-- Эта миграция создаёт основную таблицу "predictions" и индексы.
-- Допущения:
--  - Основной провайдер данных: SportMonks (fixture_id, league_id, season_id, team_id)
--  - Версионирование модели/кэша и калибровок хранится текстом
--  - Доп. рынки (totals, btts и т.п.) и мета — в JSONB для гибкости

BEGIN;

-- На случай отсутствия расширений, используем базовые типы. UUID не обязателен.
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS predictions (
    id                  BIGSERIAL PRIMARY KEY,

    -- ИДы матча/команд/лиги из SportMonks
    fixture_id          BIGINT      NOT NULL,
    league_id           BIGINT      NULL,
    season_id           BIGINT      NULL,
    home_team_id        BIGINT      NULL,
    away_team_id        BIGINT      NULL,

    -- Временной контекст
    match_start         TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Версионирование и конфигурация модели/кэша/калибраторов
    model_name          TEXT        NOT NULL DEFAULT 'poisson',
    model_version       TEXT        NOT NULL,          -- например: vYYYYMMDD
    cache_version       TEXT        NULL,              -- например: v3
    calibration_method  TEXT        NULL,              -- 'platt' | 'isotonic' | 'beta' | NULL
    model_flags         JSONB       NULL,              -- { "enable_bivariate_poisson": true, ... }

    -- Основные параметры Пуассона
    lambda_home         NUMERIC(8,4) NOT NULL,         -- λ_home
    lambda_away         NUMERIC(8,4) NOT NULL,         -- λ_away

    -- Ожидаемый тотал (λ_home + λ_away)
    expected_total      NUMERIC(8,4) GENERATED ALWAYS AS (lambda_home + lambda_away) STORED,

    -- Вероятности исходов 1X2 (калиброванные/финальные)
    prob_home_win       NUMERIC(6,5) NOT NULL,         -- [0..1]
    prob_draw           NUMERIC(6,5) NOT NULL,         -- [0..1]
    prob_away_win       NUMERIC(6,5) NOT NULL,         -- [0..1]

    -- Вероятности рынков в JSONB (гибкая структура):
    -- totals_probs: { "over": 0.53, "under": 0.47, "line": 2.5 } (можно хранить несколько линий массивом)
    -- btts_probs:   { "yes": 0.56, "no": 0.44 }
    totals_probs        JSONB       NULL,
    btts_probs          JSONB       NULL,

    -- Вероятности «скорректированные корреляцией» (Bivariate Poisson), если применялись
    totals_corr_probs   JSONB       NULL,
    btts_corr_probs     JSONB       NULL,

    -- Уверенность и штрафы
    confidence          NUMERIC(6,5) NOT NULL,        -- [0..1] итоговая уверенность
    missing_ratio       NUMERIC(6,5) NULL,            -- доля заглушек/пропусков [0..1]
    data_freshness_min  NUMERIC(10,2) NULL,           -- «возраст» данных в минутах
    penalties           JSONB       NULL,             -- детализация штрафов/коэффициентов

    -- Рекомендации (список объектов): [{ "market":"1x2","pick":"home","confidence":0.82, ... }, ...]
    recommendations     JSONB       NULL,

    -- Снимок входных признаков / контекст (для аудита/воспроизводимости)
    features_snapshot   JSONB       NULL,
    meta                JSONB       NULL,             -- произвольная служебная мета

    -- Итог матча (может быть NULL до завершения)
    final_home_goals    SMALLINT    NULL,
    final_away_goals    SMALLINT    NULL,
    outcome_1x2         TEXT        NULL,             -- 'home'|'draw'|'away' после матча
    settled_at          TIMESTAMPTZ NULL,

    -- Ограничения корректности
    CONSTRAINT chk_prob_home_win_range CHECK (prob_home_win >= 0 AND prob_home_win <= 1),
    CONSTRAINT chk_prob_draw_range     CHECK (prob_draw     >= 0 AND prob_draw     <= 1),
    CONSTRAINT chk_prob_away_win_range CHECK (prob_away_win >= 0 AND prob_away_win <= 1),
    CONSTRAINT chk_confidence_range    CHECK (confidence    >= 0 AND confidence    <= 1),
    CONSTRAINT chk_missing_ratio_range CHECK (missing_ratio IS NULL OR (missing_ratio >= 0 AND missing_ratio <= 1)),
    -- мягкая проверка суммы 1X2 (допуск на калибровку/округление ±0.01)
    CONSTRAINT chk_prob_1x2_sum_soft   CHECK (abs((prob_home_win + prob_draw + prob_away_win) - 1.0) <= 0.01),
    CONSTRAINT chk_outcome_1x2 CHECK (outcome_1x2 IN ('home','draw','away') OR outcome_1x2 IS NULL),
    CONSTRAINT chk_lambda_positive CHECK (lambda_home >= 0 AND lambda_away >= 0)
);

-- Полезные индексы
CREATE INDEX IF NOT EXISTS idx_predictions_fixture_id     ON predictions (fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_match_start    ON predictions (match_start);
CREATE INDEX IF NOT EXISTS idx_predictions_model_version  ON predictions (model_version);
CREATE INDEX IF NOT EXISTS idx_predictions_cache_version  ON predictions (cache_version);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence     ON predictions (confidence DESC);
-- GIN индексы оставляем минимально необходимыми
CREATE INDEX IF NOT EXISTS idx_predictions_reco_gin       ON predictions USING GIN (recommendations);

-- Индексы для быстрого поиска активных и завершённых матчей
CREATE INDEX IF NOT EXISTS idx_predictions_match_start_settled
    ON predictions (match_start) WHERE settled_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_predictions_settled
    ON predictions (settled_at) WHERE settled_at IS NOT NULL;

-- Уникальность: прогноз на матч от конкретной версии модели
ALTER TABLE predictions
    ADD CONSTRAINT uniq_predictions_fixture_model UNIQUE (fixture_id, model_version);

-- Триггер на автообновление updated_at
CREATE OR REPLACE FUNCTION trg_predictions_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS predictions_touch_updated_at ON predictions;
CREATE TRIGGER predictions_touch_updated_at
BEFORE UPDATE ON predictions
FOR EACH ROW
EXECUTE FUNCTION trg_predictions_touch_updated_at();

COMMIT;

