#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-critical}"

run_backend_critical() {
  python3 -m pytest -q \
    "$ROOT_DIR/backend/tests/test_publication_workflow.py" \
    "$ROOT_DIR/backend/tests/test_report_quality_checklist.py" \
    "$ROOT_DIR/backend/tests/test_engine_coverage_validation.py" \
    "$ROOT_DIR/backend/tests/test_advanced_data_mining_p2.py" \
    "$ROOT_DIR/backend/tests/test_llm_providers.py" \
    "$ROOT_DIR/backend/tests/test_data_editing_sync.py::test_update_cell_sync"
}

run_backend_full() {
  (cd "$ROOT_DIR/backend" && python3 -m pytest -q)
}

run_frontend_suite() {
  (
    cd "$ROOT_DIR/frontend"
    npm run test:run
    npm run lint
    npm run build
  )
}

echo "[preflight] mode=$MODE"
echo "[preflight] backend checks..."
if [[ "$MODE" == "full" ]]; then
  run_backend_full
else
  run_backend_critical
fi

echo "[preflight] frontend checks..."
run_frontend_suite

echo "[preflight] docker compose validation..."
if command -v docker >/dev/null 2>&1; then
  docker compose -f "$ROOT_DIR/docker-compose.yml" config >/dev/null
else
  echo "[preflight] docker is not installed; skip docker-compose validation"
fi

echo "[preflight] PASS"
