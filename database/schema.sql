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
