# StatProject Release Notes (2026-03-01)

## Scope

Production-baseline hardening for end-to-end research workflow:

- run state and verifier-driven execution remain stable,
- release bundle reproducibility is enforced and tested,
- publication/reporting flow is covered by smoke gates,
- operational runbook and backup/restore scripts are in place.

## Key Additions

- Operator runbook:
  - `/Users/eduardbelskih/Проекты Github/statproject/docs/OPERATOR_RUNBOOK.md`
- Model-router benchmark contour:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/scripts/benchmark_model_router.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/scripts/run_model_router_benchmark_capture.py` (real benchmark capture: variant planning + execute artifact + snapshot rebuild)
    - updated with `--allow-empty` mode for non-blocking CI runs without eligible datasets
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/api/v2.py` (`GET /api/v1/v2/analysis/benchmark/model-router` now includes normalized `capture_last` live summary)
  - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/CopilotPage.jsx` (historical benchmark snapshot in UI, auto-load on open, active profile winner marker, live-capture status/details)
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/release_production_smoke.sh` (production smoke now includes benchmark build + benchmark contract checks + optional strict coverage via `BENCHMARK_MIN_RUNS`/`BENCHMARK_STRICT` + optional real capture via `BENCHMARK_CAPTURE_RUN=1`)
  - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/nightly-model-router-benchmark.yml` (manual inputs for `min_runs` and optional strict coverage failure)
    - manual `capture_run` input to run live capture before snapshot
  - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/ci.yml` (benchmark contract gate on every PR/push)
- Production smoke gate script:
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/release_production_smoke.sh`
- Backup and restore scripts:
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/ops_backup_workspace.sh`
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/ops_restore_workspace.sh`
- DoD evidence tests:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_agent_orchestrator.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_release_bundle.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/pageSizeGuard.test.js`

## Verification Snapshot

- Full backend suite: `402 passed, 8 skipped`.
- Frontend: lint + unit tests + build pass.
- Production smoke report:
  - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_2026-03-01.md`
  - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_230435.md`
  - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_231154.md`
  - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_231352.md`
  - result: `overall_status: PASS`.
- Model-router empirical snapshot:
  - `/Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.json`
  - current: `runs_total=3`, `variants_total=15`, focused profile recommendations are split (`minimax_single` / `gemini_single` / `routerai_combo`, each `33.3%`).
- Planner/LLM robustness:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py` (balanced JSON extraction + local syntax repair for near-JSON outputs)
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_llm_json_parsing.py` (regression for malformed JSON recovery without extra retry round)

## Remaining Formal Action

- Create git tag and publish release entry using this note and:
  - `/Users/eduardbelskih/Проекты Github/statproject/CHANGELOG.md`.
