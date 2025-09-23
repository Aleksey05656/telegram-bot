#!/usr/bin/env bash
# /**
#  * @file: tools/ci_assert_no_binaries.sh
#  * @description: Guardrail to block binary artefacts in pull requests.
#  * @dependencies: git
#  * @created: 2025-10-12
#  */
set -euo pipefail
BASE="${GITHUB_BASE_SHA:-origin/main}"
HEAD="${GITHUB_SHA:-HEAD}"
CHANGED=$(git diff --name-only "$BASE...$HEAD" || true)
FORBID_RE='\.((png|jpe?g|gif|pdf|parquet|sqlite3?|db|zip))$'
VIOL=$(echo "$CHANGED" | grep -E "$FORBID_RE" || true)
if [ -n "$VIOL" ]; then
  echo "ERROR: Binary files are not allowed in PR:"
  echo "$VIOL"
  exit 1
fi
exit 0
