# Diagnostics Summary

| Section | Status | Notes |
| --- | --- | --- |
| ENV | ⚠️ | missing_in_example=['DATABASE_MAX_OVERFLOW', 'DATABASE_POOL_SIZE', 'DATABASE_POOL_TIMEOUT', 'DB_HOST', 'DB_NAME', 'DB_PASSWORD', 'DB_PORT', 'DB_USER', 'OFFLINE_CFG', 'PRECOMMIT', 'PREDICTIONS_DB_URL', 'RUNTIME_SCHEDULER_STATE'] extra=['ENV', 'PROMETHEUS__ENABLED', 'PROMETHEUS__ENDPOINT', 'PYTHONUNBUFFERED', 'RATE_LIMIT_ENABLED', 'RATE_LIMIT_PER_SECONDS', 'RATE_LIMIT_REQUESTS', 'SENTRY__DSN', 'SENTRY__ENABLED', 'SENTRY__ENVIRONMENT'] |
| Paths | ✅ | DB_PATH -> /workspace/telegram-bot/.tmpdata/bot.sqlite3; REPORTS_DIR -> /workspace/telegram-bot/reports; MODEL_REGISTRY_PATH -> /workspace/telegram-bot/.tmpdata/artifacts; LOG_DIR -> /workspace/telegram-bot/.tmpdata/logs; BACKUP_DIR -> /workspace/telegram-bot/.tmpdata/backups; RUNTIME_LOCK_PATH -> /workspace/telegram-bot/.tmpdata/runtime.lock |
| Smoke | ✅ | rc=0 log=/workspace/telegram-bot/reports/diagnostics/smoke.log |
| Model Level A | ✅ | alpha=0.5 folds=4 |
| Model Level B | ✅ | Δlogloss=-0.0593 |
| Model Level C | ✅ | home_win=0.403 |
| Backtest | ✅ | logloss=0.991 brier=0.591 |
| Bot UX | ✅ | latency_ms≈0.1 |
| Ops | ✅ | health=HTTP/1.1 200 OK ready=HTTP/1.1 200 OK |

## Context

```json
{
  "entry": {
    "entry_point": "python -m main",
    "script": "/workspace/telegram-bot/main.py",
    "flags": [
      "dry-run"
    ]
  },
  "reports_dir": "/workspace/telegram-bot/reports/diagnostics",
  "settings_snapshot": {
    "DB_PATH": "/workspace/telegram-bot/.tmpdata/bot.sqlite3",
    "REPORTS_DIR": "/workspace/telegram-bot/reports",
    "MODEL_REGISTRY_PATH": "/workspace/telegram-bot/.tmpdata/artifacts"
  }
}
```

## Metrics Snapshot

```json
{
  "smoke": {
    "returncode": 0,
    "stdout_tail": "time=2025-09-23T10:01:52.110865Z level=info logger=amvera message=\"✅ Хранилище FSM закрыто\"\ntime=2025-09-23T10:01:52.110947Z level=info logger=amvera message=\"✅ Ресурсы бота освобождены\"\ntime=2025-09-23T10:01:52.111017Z level=info logger=amvera message=\"🧹 Начало очистки ресурсов бота...\"\ntime=2025-09-23T10:01:52.111094Z level=info logger=amvera message=\"✅ Сессия бота закрыта\"\ntime=2025-09-23T10:01:52.111163Z level=info logger=amvera message=\"✅ Хранилище FSM закрыто\"\ntime=2025-09-23T10:01:52.111241Z level=info logger=amvera message=\"✅ Ресурсы бота освобождены\"\ntime=2025-09-23T10:01:52.111317Z level=info logger=amvera message=\"Завершение приложения...\"\ntime=2025-09-23T10:01:52.111741Z level=info logger=amvera message=\"Health server stopped\"\ntime=2025-09-23T10:01:52.112437Z level=info logger=amvera message=\"✅ Ресурсы приложения освобождены\"\ntime=2025-09-23T10:01:52.113009Z level=info logger=amvera message=\"Runtime lock released at /workspace/telegram-bot/.tmpdata/runtime.lock\"",
    "stderr_tail": "",
    "log": "/workspace/telegram-bot/reports/diagnostics/smoke.log",
    "notes": []
  },
  "dataset_hash": "944d770dd412c6837711e5eca7aa06a001853f2b4f08266f233e5f71d3d2a49b",
  "env_contract": {
    "example_keys": [
      "ADMIN_IDS",
      "APP_NAME",
      "APP_VERSION",
      "BACKUP_DIR",
      "BACKUP_KEEP",
      "CACHE_TTL_SECONDS",
      "DATABASE_URL",
      "DATA_ROOT",
      "DB_PATH",
      "DEBUG",
      "DIGEST_DEFAULT_TIME",
      "ENABLE_HEALTH",
      "ENABLE_METRICS",
      "ENABLE_POLLING",
      "ENABLE_SCHEDULER",
      "ENV",
      "FAILSAFE_MODE",
      "GIT_SHA",
      "HEALTH_HOST",
      "HEALTH_PORT",
      "LOG_DIR",
      "LOG_LEVEL",
      "METRICS_PORT",
      "MODEL_REGISTRY_PATH",
      "ODDS_API_KEY",
      "PAGINATION_PAGE_SIZE",
      "PROMETHEUS__ENABLED",
      "PROMETHEUS__ENDPOINT",
      "PYTHONUNBUFFERED",
      "RATE_LIMIT_ENABLED",
      "RATE_LIMIT_PER_SECONDS",
      "RATE_LIMIT_REQUESTS",
      "REDIS_DB",
      "REDIS_HOST",
      "REDIS_PORT",
      "REPORTS_DIR",
      "RETRAIN_CRON",
      "RETRY_ATTEMPTS",
      "RETRY_BACKOFF",
      "RETRY_DELAY",
      "RETRY_MAX_DELAY",
      "RUNTIME_LOCK_PATH",
      "SEASON_ID",
      "SENTRY__DSN",
      "SENTRY__ENABLED",
      "SENTRY__ENVIRONMENT",
      "SHUTDOWN_TIMEOUT",
      "SIM_CHUNK",
      "SIM_N",
      "SIM_RHO",
      "SPORTMONKS_API_KEY",
      "SPORTMONKS_STUB",
      "STARTUP_DELAY_SEC",
      "TELEGRAM_BOT_TOKEN"
    ],
    "getenv_keys": [
      "APP_NAME",
      "DATABASE_MAX_OVERFLOW",
      "DATABASE_POOL_SIZE",
      "DATABASE_POOL_TIMEOUT",
      "DATABASE_URL",
      "DATA_ROOT",
      "DB_HOST",
      "DB_NAME",
      "DB_PASSWORD",
      "DB_PATH",
      "DB_PORT",
      "DB_USER",
      "DEBUG",
      "MODEL_REGISTRY_PATH",
      "ODDS_API_KEY",
      "OFFLINE_CFG",
      "PRECOMMIT",
      "PREDICTIONS_DB_URL",
      "REPORTS_DIR",
      "RETRAIN_CRON",
      "RUNTIME_SCHEDULER_STATE",
      "SEASON_ID",
      "SIM_CHUNK",
      "SPORTMONKS_API_KEY",
      "SPORTMONKS_STUB",
      "TELEGRAM_BOT_TOKEN"
    ],
    "settings_fields": [
      "ADMIN_IDS",
      "APP_ENV",
      "APP_VERSION",
      "BACKUP_DIR",
      "BACKUP_KEEP",
      "CACHE_TTL_SECONDS",
      "CACHE_VERSION",
      "CALIBRATION_METHOD",
      "CONFIDENCE",
      "CV_GAP_DAYS",
      "CV_MIN_TRAIN_DAYS",
      "CV_N_SPLITS",
      "DATABASE_CONNECT_TIMEOUT",
      "DATABASE_ECHO",
      "DATABASE_MAX_OVERFLOW",
      "DATABASE_POOL_SIZE",
      "DATABASE_POOL_TIMEOUT",
      "DATABASE_SQLITE_TIMEOUT",
      "DATABASE_STATEMENT_TIMEOUT_MS",
      "DATABASE_URL",
      "DATABASE_URL_R",
      "DATABASE_URL_RO",
      "DATA_ROOT",
      "DB_PATH",
      "DEBUG_MODE",
      "DIGEST_DEFAULT_TIME",
      "ENABLE_HEALTH",
      "ENABLE_METRICS",
      "ENABLE_POLLING",
      "ENABLE_SCHEDULER",
      "FAILSAFE_MODE",
      "GIT_SHA",
      "HEALTH_HOST",
      "HEALTH_PORT",
      "LOG_DIR",
      "LOG_LEVEL",
      "METRICS_PORT",
      "MODELS_DIR",
      "MODEL_FLAGS",
      "MODEL_REGISTRY_PATH",
      "MODEL_VERSION",
      "MODEL_VERSION_FORMAT",
      "ODDS_API_KEY",
      "PAGINATION_PAGE_SIZE",
      "POISSON_MODEL_PATH",
      "PREDICTION_LOCK_BLOCKING_TIMEOUT",
      "PREDICTION_LOCK_TIMEOUT",
      "PROMETHEUS_PORT",
      "REDIS_DB",
      "REDIS_HOST",
      "REDIS_PASSWORD",
      "REDIS_PORT",
      "REPORTS_DIR",
      "RETRY_ATTEMPTS",
      "RETRY_BACKOFF",
      "RETRY_DELAY",
      "RETRY_MAX_DELAY",
      "RUNTIME_LOCK_PATH",
      "SENTRY_DSN",
      "SHUTDOWN_TIMEOUT",
      "SIM_CHUNK",
      "SIM_N",
      "SIM_RHO",
      "SIM_SEED",
      "SPORTMONKS_API_KEY",
      "STARTUP_DELAY_SEC",
      "TELEGRAM_BOT_TOKEN",
      "TIME_DECAY_HALFLIFE_DAYS",
      "TTL",
      "XGBOOST_MODEL_PATH"
    ],
    "missing_in_example": [
      "DATABASE_MAX_OVERFLOW",
      "DATABASE_POOL_SIZE",
      "DATABASE_POOL_TIMEOUT",
      "DB_HOST",
      "DB_NAME",
      "DB_PASSWORD",
      "DB_PORT",
      "DB_USER",
      "OFFLINE_CFG",
      "PRECOMMIT",
      "PREDICTIONS_DB_URL",
      "RUNTIME_SCHEDULER_STATE"
    ],
    "extra_in_example": [
      "ENV",
      "PROMETHEUS__ENABLED",
      "PROMETHEUS__ENDPOINT",
      "PYTHONUNBUFFERED",
      "RATE_LIMIT_ENABLED",
      "RATE_LIMIT_PER_SECONDS",
      "RATE_LIMIT_REQUESTS",
      "SENTRY__DSN",
      "SENTRY__ENABLED",
      "SENTRY__ENVIRONMENT"
    ],
    "settings_only": [
      "APP_ENV",
      "CACHE_VERSION",
      "CALIBRATION_METHOD",
      "CONFIDENCE",
      "CV_GAP_DAYS",
      "CV_MIN_TRAIN_DAYS",
      "CV_N_SPLITS",
      "DATABASE_CONNECT_TIMEOUT",
      "DATABASE_ECHO",
      "DATABASE_MAX_OVERFLOW",
      "DATABASE_POOL_SIZE",
      "DATABASE_POOL_TIMEOUT",
      "DATABASE_SQLITE_TIMEOUT",
      "DATABASE_STATEMENT_TIMEOUT_MS",
      "DATABASE_URL_R",
      "DATABASE_URL_RO",
      "DEBUG_MODE",
      "MODELS_DIR",
      "MODEL_FLAGS",
      "MODEL_VERSION",
      "MODEL_VERSION_FORMAT",
      "POISSON_MODEL_PATH",
      "PREDICTION_LOCK_BLOCKING_TIMEOUT",
      "PREDICTION_LOCK_TIMEOUT",
      "PROMETHEUS_PORT",
      "REDIS_PASSWORD",
      "SENTRY_DSN",
      "SIM_SEED",
      "TIME_DECAY_HALFLIFE_DAYS",
      "TTL",
      "XGBOOST_MODEL_PATH"
    ]
  },
  "level_a": {
    "folds": [
      {
        "fold": 0,
        "logloss": 1.012336001746006,
        "brier": 0.6015153874039754
      },
      {
        "fold": 1,
        "logloss": 1.1693497454360255,
        "brier": 0.6923021020050931
      },
      {
        "fold": 2,
        "logloss": 1.064847873755901,
        "brier": 0.629979026894854
      },
      {
        "fold": 3,
        "logloss": 1.1346287562330264,
        "brier": 0.6714942354936362
      }
    ],
    "best_alpha": 0.5,
    "feature_ranking": [
      [
        "motivation",
        0.186214819527921
      ],
      [
        "away_xga",
        0.17062536201036477
      ],
      [
        "home_xg",
        0.10536667064662686
      ],
      [
        "home_xga",
        0.10377444831827871
      ],
      [
        "fatigue",
        0.09835789366431076
      ],
      [
        "away_xg",
        0.0710750412682325
      ],
      [
        "away_league_zscore_attack",
        0.03414750684722421
      ],
      [
        "home_oppda",
        0.022067912910811453
      ],
      [
        "away_ppda",
        0.02084556324096433
      ],
      [
        "injuries",
        0.01643478607833052
      ],
      [
        "away_league_zscore_defense",
        0.014943665115841958
      ],
      [
        "away_rest_days",
        0.011535809608665477
      ],
      [
        "home_ppda",
        0.009568755939257814
      ],
      [
        "away_oppda",
        0.008327296301252575
      ],
      [
        "home_league_zscore_defense",
        0.00799855313904866
      ],
      [
        "home_rest_days",
        0.0075015366453927215
      ],
      [
        "home_league_zscore_attack",
        0.0019227661703268874
      ]
    ],
    "lambda_stats": {
      "lambda_home_mean": 0.5250528349234606,
      "lambda_away_mean": 0.3986786272697299,
      "lambda_home_std": 0.7116206237304427,
      "lambda_away_std": 0.5774704275867956,
      "mae_home": 0.8260014326642164,
      "mae_away": 0.6598593613956312
    },
    "artifact": "/workspace/telegram-bot/reports/diagnostics/level_a_predictions.csv"
  },
  "level_b": {
    "monotonic_checks": {
      "home_motivation": 0.0,
      "home_fatigue": -0.0,
      "home_injuries": -0.0
    },
    "ablation": {
      "logloss_base": 1.1670930381924185,
      "logloss_mod": 1.1077627112795168,
      "brier_base": 0.7184791261895382,
      "brier_mod": 0.6735558588592649
    },
    "artifact": "/workspace/telegram-bot/reports/diagnostics/level_b_modifiers.csv"
  },
  "level_c": {
    "markets": {
      "home_win": 0.4028,
      "draw": 0.2806,
      "away_win": 0.3166,
      "over_2_5": 0.3752,
      "over_3_5": 0.1766,
      "btts": 0.44,
      "fair_prices": {
        "1": 2.48,
        "X": 3.56,
        "2": 3.16,
        "BTTS": 2.27
      }
    },
    "top_scores": [
      [
        "1-0",
        0.1344
      ],
      [
        "1-1",
        0.1336
      ],
      [
        "0-1",
        0.1146
      ],
      [
        "0-0",
        0.1072
      ],
      [
        "2-1",
        0.079
      ],
      [
        "2-0",
        0.0782
      ],
      [
        "1-2",
        0.0686
      ],
      [
        "0-2",
        0.0568
      ],
      [
        "2-2",
        0.0348
      ],
      [
        "3-0",
        0.0326
      ]
    ],
    "calibration": {
      "over25_curve": {
        "pred": [
          0.17079932313060084,
          0.21909552082760964,
          0.24471781853801092,
          0.2626875378515546,
          0.2829094763482971,
          0.30371562923071965,
          0.3321527150804513,
          0.3897375061140859
        ],
        "observed": [
          0.17391304347826086,
          0.36363636363636365,
          0.2608695652173913,
          0.18181818181818182,
          0.36363636363636365,
          0.391304347826087,
          0.4090909090909091,
          0.6086956521739131
        ]
      }
    },
    "artifacts": {
      "reliability": "",
      "totals": "",
      "scorelines": "",
      "gain": ""
    }
  },
  "backtest": {
    "aggregate": {
      "logloss": 0.9907179298061948,
      "brier": 0.5905439364370247,
      "roc_auc_btts": 0.5933704453441295,
      "roc_auc_over": 0.6474849644614544
    },
    "csv": "/workspace/telegram-bot/reports/diagnostics/backtest_summary.csv"
  },
  "bot": {
    "latency": {
      "/start": 0.02,
      "/help": 0.0,
      "/today": 0.32,
      "/match": 0.13,
      "/explain": 0.03,
      "/settings": 0.0,
      "/about": 0.01
    },
    "html_lengths": {
      "start": 287,
      "help": 507,
      "today": 271,
      "match": 441,
      "explain": 360,
      "settings": 91,
      "about": 80
    },
    "reports": [
      {
        "report_id": "diag-report",
        "match_id": 4242,
        "path": "/tmp/report.csv",
        "created_at": "2025-09-23 10:01:12"
      },
      {
        "report_id": "png:777",
        "match_id": 777,
        "path": "/tmp/pytest-of-root/pytest-1/test_generate_csv_and_png0/match_777.png",
        "created_at": "2025-09-23 09:55:35"
      },
      {
        "report_id": "csv:777",
        "match_id": 777,
        "path": "/tmp/pytest-of-root/pytest-1/test_generate_csv_and_png0/match_777.csv",
        "created_at": "2025-09-23 09:55:35"
      }
    ],
    "keyboards": {
      "today_buttons": 2,
      "match_buttons": 2
    },
    "payloads_artifact": "/workspace/telegram-bot/reports/diagnostics/bot_payloads.json",
    "cache_ttl": 120
  },
  "ops": {
    "health_response": "HTTP/1.1 200 OK",
    "ready_response": "HTTP/1.1 200 OK",
    "runtime_lock": true,
    "backups": [
      "/workspace/telegram-bot/.tmpdata/backups/bot-20250923-100151.sqlite3"
    ]
  }
}
```