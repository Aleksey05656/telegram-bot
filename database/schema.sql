--
-- schema.sql — SQLite schema for bot user preferences and reports
-- Generated on 2025-09-23
--
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS user_prefs (
    user_id INTEGER PRIMARY KEY,
    tz TEXT NOT NULL DEFAULT 'UTC',
    lang TEXT NOT NULL DEFAULT 'ru',
    odds_format TEXT NOT NULL DEFAULT 'decimal',
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER NOT NULL,
    league TEXT NULL,
    send_at TEXT NOT NULL,
    tz TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    match_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

CREATE TABLE IF NOT EXISTS sm_fixtures (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NULL,
    season_id INTEGER NULL,
    home_id INTEGER NULL,
    away_id INTEGER NULL,
    kickoff_utc TEXT NULL,
    status TEXT NULL,
    payload_json TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sm_fixtures_kickoff ON sm_fixtures(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_sm_fixtures_league ON sm_fixtures(league_id);
CREATE INDEX IF NOT EXISTS idx_sm_fixtures_season ON sm_fixtures(season_id);

CREATE TABLE IF NOT EXISTS sm_teams (
    id INTEGER PRIMARY KEY,
    name_norm TEXT NOT NULL,
    country TEXT NULL,
    payload_json TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sm_teams_name_norm ON sm_teams(name_norm);

CREATE TABLE IF NOT EXISTS sm_standings (
    league_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    position INTEGER NULL,
    points INTEGER NULL,
    payload_json TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL,
    PRIMARY KEY (league_id, season_id, team_id)
);
CREATE INDEX IF NOT EXISTS idx_sm_standings_position ON sm_standings(position);

CREATE TABLE IF NOT EXISTS sm_injuries (
    id INTEGER PRIMARY KEY,
    fixture_id INTEGER NULL,
    team_id INTEGER NULL,
    player_name TEXT NOT NULL,
    status TEXT NULL,
    payload_json TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sm_injuries_team ON sm_injuries(team_id);

CREATE TABLE IF NOT EXISTS sm_meta (
    key TEXT PRIMARY KEY,
    value_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS map_teams (
    sm_team_id INTEGER PRIMARY KEY,
    internal_team_id INTEGER NOT NULL,
    name_norm TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_map_teams_name_norm ON map_teams(name_norm);

CREATE TABLE IF NOT EXISTS map_leagues (
    sm_league_id INTEGER PRIMARY KEY,
    internal_code TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL,
    match_key TEXT NOT NULL,
    league TEXT NULL,
    kickoff_utc TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    price_decimal REAL NOT NULL,
    extra_json TEXT NULL,
    UNIQUE(provider, match_key, market, selection, pulled_at_utc)
);

CREATE INDEX IF NOT EXISTS idx_odds_snapshots_match
    ON odds_snapshots(match_key, market, selection);

CREATE INDEX IF NOT EXISTS idx_odds_snapshots_match_time
    ON odds_snapshots(match_key, market, selection, pulled_at_utc);

CREATE TABLE IF NOT EXISTS value_alerts (
    user_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    edge_threshold REAL NOT NULL DEFAULT 5.0,
    league TEXT NULL,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS value_calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league TEXT NOT NULL,
    market TEXT NOT NULL,
    tau_edge REAL NOT NULL,
    gamma_conf REAL NOT NULL,
    samples INTEGER NOT NULL,
    metric REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    UNIQUE(league, market)
);

CREATE INDEX IF NOT EXISTS value_calibration_idx
    ON value_calibration(league, market);

CREATE TABLE IF NOT EXISTS value_alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_key TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    edge_pct REAL NOT NULL,
    UNIQUE(user_id, match_key, market, selection, sent_at)
);

CREATE INDEX IF NOT EXISTS value_alerts_sent_idx
    ON value_alerts_sent(user_id, match_key, market, selection, sent_at);

CREATE TABLE IF NOT EXISTS closing_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_key TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    consensus_price REAL NOT NULL,
    consensus_probability REAL NOT NULL,
    provider_count INTEGER NOT NULL,
    method TEXT NOT NULL,
    pulled_at_utc TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    UNIQUE(match_key, market, selection)
);

CREATE TABLE IF NOT EXISTS picks_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_key TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    stake REAL NOT NULL DEFAULT 1.0,
    price_taken REAL NOT NULL,
    provider_price_decimal REAL NOT NULL DEFAULT 0.0,
    model_probability REAL NOT NULL,
    market_probability REAL NOT NULL,
    edge_pct REAL NOT NULL,
    confidence REAL NOT NULL,
    pulled_at_utc TEXT NOT NULL,
    kickoff_utc TEXT NOT NULL,
    consensus_price REAL NOT NULL,
    consensus_price_decimal REAL NOT NULL DEFAULT 0.0,
    consensus_method TEXT NOT NULL,
    consensus_provider_count INTEGER NOT NULL,
    clv_pct REAL NULL,
    outcome TEXT NULL,
    roi REAL NULL,
    closing_price REAL NULL,
    closing_pulled_at TEXT NULL,
    closing_method TEXT NULL,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now')),
    UNIQUE(user_id, match_key, market, selection, pulled_at_utc)
);

CREATE INDEX IF NOT EXISTS picks_ledger_user_idx
    ON picks_ledger(user_id, created_at);

CREATE INDEX IF NOT EXISTS picks_ledger_match_idx
    ON picks_ledger(match_key, market, selection);

CREATE TABLE IF NOT EXISTS provider_stats (
    provider TEXT NOT NULL,
    market TEXT NOT NULL,
    league TEXT NOT NULL,
    coverage REAL NOT NULL,
    fresh_share REAL NOT NULL,
    lag_ms REAL NOT NULL,
    stability REAL NOT NULL,
    bias REAL NOT NULL,
    score REAL NOT NULL,
    sample_size INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(provider, market, league)
);
