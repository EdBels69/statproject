#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
cd "${REPO_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python interpreter not found (checked: ${PYTHON_BIN}, python)." >&2
    exit 1
  fi
fi

"${PYTHON_BIN}" -m pytest -q \
  backend/tests \
  -W error::RuntimeWarning \
  -W error::FutureWarning \
  -W 'ignore:SeriesGroupBy.grouper is deprecated and will be removed in a future version of pandas.:FutureWarning' \
  -W 'ignore:When grouping with a length-1 list-like, you will need to pass a length-1 tuple to get_group in a future version of pandas.:FutureWarning' \
  "$@"
