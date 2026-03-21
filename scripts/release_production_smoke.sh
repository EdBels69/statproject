#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/release"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${1:-${REPORT_DIR}/PRODUCTION_SMOKE_${STAMP}.md}"

mkdir -p "${REPORT_DIR}"
: > "${REPORT_PATH}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

OVERALL_FAIL=0

append() {
  printf "%s\n" "$1" >> "${REPORT_PATH}"
}

append "# Production Smoke Report"
append ""
append "- generated_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
append "- host: $(hostname)"
append "- repo: ${ROOT_DIR}"
append "- commit: $(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
append ""

run_step() {
  local name="$1"
  local cmd="$2"
  local out_file="${TMP_DIR}/$(echo "${name}" | tr ' /:' '___').log"

  append "## ${name}"
  append ""
  append '```bash'
  append "${cmd}"
  append '```'

  if bash -lc "${cmd}" > "${out_file}" 2>&1; then
    append ""
    append "- status: PASS"
  else
    append ""
    append "- status: FAIL"
    OVERALL_FAIL=1
  fi

  append ""
  append '```text'
  sed -n '1,160p' "${out_file}" >> "${REPORT_PATH}" || true
  append '```'
  append ""
}

run_step \
  "Backend runtime warning gate" \
  "cd '${ROOT_DIR}/backend' && ./scripts/run_runtime_warning_gate.sh"

run_step \
  "Backend release smoke tests" \
  "cd '${ROOT_DIR}/backend' && python3 -m pytest -q tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_release_bundle_strict_compare tests/test_report_quality_checklist.py::test_report_quality_endpoint_passes_with_full_artifacts tests/test_release_bundle.py::test_release_bundle_generated_script_verifies_manifest"

run_step \
  "Frontend lint" \
  "cd '${ROOT_DIR}/frontend' && npm run lint"

run_step \
  "Frontend unit tests" \
  "cd '${ROOT_DIR}/frontend' && npm run test:run"

run_step \
  "Frontend build" \
  "cd '${ROOT_DIR}/frontend' && npm run build"

if [[ "${OVERALL_FAIL}" -eq 0 ]]; then
  append "## Summary"
  append ""
  append "- overall_status: PASS"
else
  append "## Summary"
  append ""
  append "- overall_status: FAIL"
fi

echo "Smoke report saved: ${REPORT_PATH}"
if [[ "${OVERALL_FAIL}" -ne 0 ]]; then
  exit 1
fi
