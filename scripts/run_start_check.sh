#!/usr/bin/env bash
# /**
#  * @file: scripts/run_start_check.sh
#  * @description: Smoke check ensuring ROLE values with quotes do not break startup commands.
#  * @dependencies: main.py
#  * @created: 2025-11-03
#  */
set -euo pipefail
IFS=$'\n\t'

mask() {
    local value="${1-}"

    if [[ -z "${value}" ]]; then
        printf '<missing>'
        return
    fi

    local prefix="${value:0:4}"
    printf '%s***' "${prefix}"
}

export METRICS_ENABLED="false"
export SCHEDULES_ENABLED="false"
export EXTERNAL_CLIENTS_ENABLED="false"
export API_ENABLED="false"

ROLE_VALUE="${ROLE:-}"

if [[ -z "${ROLE_VALUE}" ]]; then
    echo "[error] ROLE environment variable must be set" >&2
    exit 1
fi

echo "[env] ROLE=${ROLE_VALUE}"
echo "[env] TELEGRAM_BOT_TOKEN=$(mask "${TELEGRAM_BOT_TOKEN:-}")"
echo "[env] SPORTMONKS_API_TOKEN=$(mask "${SPORTMONKS_API_TOKEN:-}")"

echo "[preflight] redis"
if python3 scripts/preflight_redis.py; then
    echo "[preflight] redis check finished"
else
    redis_status=$?
    echo "[warning] redis preflight exited with status ${redis_status}" >&2
fi

ROLE_NORMALIZED="${ROLE_VALUE,,}"
if [[ "${ROLE_NORMALIZED}" == "bot" ]]; then
    echo "[preflight] sportmonks"
    python3 scripts/preflight_sportmonks.py
fi

env ROLE="${ROLE_VALUE}" \
    USE_OFFLINE_STUBS="${USE_OFFLINE_STUBS:-1}" \
    python -m app.main --help >/dev/null

echo "OK"
