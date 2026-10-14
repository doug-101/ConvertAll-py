#!/usr/bin/env bash
# User-run only: QA, Linux packages, CI Windows executable bundle, optional draft.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${CONVERTALL_RELEASE_PYTHON:-$ROOT/.venv/test-all-qt6/bin/python}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  printf '%s\n' "Python introuvable : $PYTHON" \
    'Préparez le venv avec test_all_qt6.sh, ou définissez CONVERTALL_RELEASE_PYTHON.' >&2
  exit 2
fi
exec "$PYTHON" "$ROOT/tools/release_qt6.py" "$@"
