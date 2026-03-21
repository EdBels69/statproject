#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python interpreter not found (checked: ${PYTHON_BIN}, python)." >&2
    exit 1
  fi
fi

TESTS=(
  "tests/test_covid_smoke_v2_flow.py::test_covid_smoke_v2_python_plan_execute_report"
  "tests/test_engine_parity_advanced_batch_modes.py::test_execute_delta_batch_analysis_with_r_engine"
  "tests/test_execute_v2_advanced_coverage.py::test_execute_protocol_paired_wide_constant_no_runtime_warning"
  "tests/test_engine_kendall_and_assumptions.py::test_near_constant_normality_without_runtime_warning"
  "tests/test_descriptives.py::test_descriptives_constant_series_no_runtime_warning"
)

"${PYTHON_BIN}" -m pytest -q \
  "${TESTS[@]}" \
  -W error::RuntimeWarning \
  -o filterwarnings=ignore::pytest.PytestCollectionWarning \
  "$@"
