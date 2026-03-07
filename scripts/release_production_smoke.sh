#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/release"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${1:-${REPORT_DIR}/PRODUCTION_SMOKE_${STAMP}.md}"
BENCHMARK_MIN_RUNS="${BENCHMARK_MIN_RUNS:-0}"
BENCHMARK_STRICT="${BENCHMARK_STRICT:-0}"
BENCHMARK_CAPTURE_RUN="${BENCHMARK_CAPTURE_RUN:-0}"

BENCHMARK_STRICT_FLAG=""
if [[ "${BENCHMARK_STRICT}" == "1" || "${BENCHMARK_STRICT}" == "true" || "${BENCHMARK_STRICT}" == "TRUE" ]]; then
  BENCHMARK_STRICT_FLAG="--strict-min-runs"
fi

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
append "- benchmark_min_runs: ${BENCHMARK_MIN_RUNS}"
append "- benchmark_strict: ${BENCHMARK_STRICT}"
append "- benchmark_capture_run: ${BENCHMARK_CAPTURE_RUN}"
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

if [[ "${BENCHMARK_CAPTURE_RUN}" == "1" || "${BENCHMARK_CAPTURE_RUN}" == "true" || "${BENCHMARK_CAPTURE_RUN}" == "TRUE" ]]; then
  run_step \
    "Model-router benchmark capture run" \
    "cd '${ROOT_DIR}' && python3 backend/scripts/run_model_router_benchmark_capture.py --workspace-dir workspace --analysis-mode focused --max-protocol-steps 1 --min-runs ${BENCHMARK_MIN_RUNS} --snapshot-output release/model_router_benchmark_report.json --snapshot-markdown release/model_router_benchmark_report.md --capture-output release/model_router_benchmark_capture_last.json --pretty"
fi

run_step \
  "Model-router benchmark snapshot build" \
  "cd '${ROOT_DIR}' && python3 backend/scripts/benchmark_model_router.py --workspace-dir workspace --output release/model_router_benchmark_report.json --markdown-out release/model_router_benchmark_report.md --min-runs ${BENCHMARK_MIN_RUNS} ${BENCHMARK_STRICT_FLAG} --pretty"

run_step \
  "Backend benchmark contract tests" \
  "cd '${ROOT_DIR}/backend' && python3 -m pytest -q tests/test_api_v2.py::test_model_router_benchmark_snapshot_endpoint tests/test_model_router_benchmark.py::test_benchmark_cli_generates_json_and_markdown tests/test_model_router_benchmark.py::test_benchmark_cli_strict_min_runs_fails_when_insufficient"

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
