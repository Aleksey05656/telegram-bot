#!/usr/bin/env bash
# /**
#  * @file: scripts/entrypoint.sh
#  * @description: Container entrypoint orchestrating migrations, health checks and bot startup.
#  * @dependencies: scripts/prestart.py, main.py
#  * @created: 2025-09-21
#  */
set -euo pipefail

required_env=(DATABASE_URL REDIS_URL TELEGRAM_BOT_TOKEN)

for var in "${required_env[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        printf '{"level":"ERROR","event":"env.missing","variable":"%s"}\n' "$var" >&2
        exit 1
    fi
done

printf '{"level":"INFO","event":"prestart.invoke"}\n'
python -m scripts.prestart

printf '{"level":"INFO","event":"bot.launch","command":"python -m main"}\n'
exec python -m main
