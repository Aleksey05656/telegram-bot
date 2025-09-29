#!/usr/bin/env bash
# /**
#  * @file: scripts/run_start_check.sh
#  * @description: Smoke check ensuring ROLE values with quotes do not break startup commands.
#  * @dependencies: main.py
#  * @created: 2025-11-03
#  */
set -euo pipefail

export METRICS_ENABLED="false"
export SCHEDULES_ENABLED="false"
export EXTERNAL_CLIENTS_ENABLED="false"

ROLE_VALUE="${ROLE:-}"

echo "[run_start_check] ROLE=${ROLE_VALUE}"

env ROLE="${ROLE_VALUE}" \
    USE_OFFLINE_STUBS="${USE_OFFLINE_STUBS:-1}" \
    python -m app.main --help >/dev/null

echo "[run_start_check] Success"
