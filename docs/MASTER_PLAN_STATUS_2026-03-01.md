# Master Plan Status (2026-03-01)

## Snapshot

- Backend tests: `402 passed, 8 skipped` (`python3 -m pytest backend/tests -q`)
- Frontend tests: `42 passed` (`npm run test:run`)
- Frontend lint: clean (`npm run lint`)
- Frontend build: success (`npm run build`)

## Iteration Status

### Iteration 1 — State Machine + Contracts + Artifacts

- Status: **Done**
- Evidence:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/core/run_state_machine.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_run_state_machine.py`
  - Reporting split modules exist (`reporting_html.py`, `reporting_docx.py`, `reporting_pdf.py`)

### Iteration 2 — Robust Ingest + Cleaning + Freeze

- Status: **Done**
- Evidence:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/excel_intelligence.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/data_quality_gate.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/data_lineage.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_ingest_quality_gate_integration.py`

### Iteration 3 — Protocol Compiler + Validator + Reflect

- Status: **Done**
- Evidence:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/copilot/validator.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/copilot/reflect_agent.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_execute_v2_agent_orchestration.py`

### Iteration 4 — Verifier + Multiplicity + Bootstrap path

- Status: **Done**
- Evidence:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/copilot/verifier.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/copilot/verification_policy.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_verifier.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_verification_policy.py`

### Iteration 5 — Report v3 + Provenance + Release Bundle

- Status: **Done**
- Evidence:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_release_bundle.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_reporting_manuscript_sections.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_e2e_upload_analyze_export.py`
  - Frontend page-size guard:
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/pageSizeGuard.test.js`

### Iteration 6 — Agent Orchestrator + NLQ + CI + Benchmarks

- Status: **Done**
  - Done evidence:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/copilot/orchestrator.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_agent_orchestrator.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_nlq_router.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/ci.yml` (frontend gate + backend full tests + runtime warning gate + benchmark contract gate)
- Optimization backlog (closed in this cycle):
  - Prompt/ranking quality tuning for model-router on real clinical corpora: **Done (baseline heuristic tuning)**
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/components/benchmarkScoring.js` (profile-aware ranking: publication/focused/exploratory)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/api/v2.py` (`benchmark_context` normalization + profile-aware server auto-recommendation)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_llm_benchmark_payload.py` (regression for profile-aware recommendations)
  - Empirical corpus harness for router benchmarking: **Done**
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/model_router_benchmark.py` (aggregation of `llm_benchmark` artifacts + winners/stability summary)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/scripts/benchmark_model_router.py` (CLI report builder, `min_runs` coverage gate, Markdown summary)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_model_router_benchmark.py` (workspace fixture regression)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/api/v2.py` (`GET /api/v1/v2/analysis/benchmark/model-router` snapshot endpoint)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_api_v2.py` (endpoint regression)
    - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/nightly-model-router-benchmark.yml` (nightly/manual benchmark snapshot artifact, JSON+MD upload)
  - Runtime profiling for large exploratory protocols: **Done**
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/api/v2.py` (`runtime_profile` in execute-v2 response + run artifact + reproducibility manifest)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_execute_v2_advanced_coverage.py` (artifact/manifest regression)
  - Optional UX polish in report visual layer: **Done (terminology cleanup)**
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting_html.py` (no raw correction codes in policy table when label exists)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting_docx.py` (human-readable correction labels without `[fdr_bh]` suffixes)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_reporting_batch_tables.py` (regression assertion against raw code suffixes)
  - Operator contour for benchmark monitoring: **Done**
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/lib/api.js` (`getModelRouterBenchmarkSnapshot`)
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/CopilotPage.jsx` (historical benchmark snapshot block with winners/coverage/top variants + auto-load on page open + active profile winner marker)
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/CopilotPage.test.jsx` (snapshot UI regression)
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/lib/api.test.js` (snapshot API regression)
    - `/Users/eduardbelskih/Проекты Github/statproject/docs/OPERATOR_RUNBOOK.md` (section "Model Router Benchmark Operations")
    - `/Users/eduardbelskih/Проекты Github/statproject/scripts/release_production_smoke.sh` (benchmark build + benchmark contract checks in production smoke + env-controlled strict coverage gate)
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_model_router_benchmark.py` (CLI regression for JSON/Markdown benchmark outputs + strict min-runs failure case)
    - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/nightly-model-router-benchmark.yml` (workflow_dispatch inputs for min_runs/strict coverage)

### Post-Baseline Hardening — Time-Series Chronology Quality (2026-03-01)

- Status: **Done**
- Done evidence:
  - Runtime chronology quality diagnostics in engine payload:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/stats/engine.py` (`time_quality`, quality flags, human-readable warnings)
  - Report parity for chronology diagnostics across formats:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting_html.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting_docx.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting_pdf.py`
  - Frontend visualization diagnostics panel for time-series:
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/AnalyticsChart.jsx`
  - Regression tests:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_engine_advanced_methods_dispatch.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_reporting_batch_tables.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_reporting_design_quality.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/AnalyticsChart.test.jsx`

### Post-Baseline Hardening — Model Router Benchmark Real Capture (2026-03-01)

- Status: **Done**
- Done evidence:
  - Real benchmark capture CLI (plan variants -> execute -> `llm_benchmark` artifact -> snapshot rebuild):
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/scripts/run_model_router_benchmark_capture.py`
  - Production smoke supports optional real capture step (`BENCHMARK_CAPTURE_RUN=1`):
    - `/Users/eduardbelskih/Проекты Github/statproject/scripts/release_production_smoke.sh`
  - Capture CLI supports non-blocking CI mode on empty workspace (`--allow-empty`) with explicit skipped artifact status:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/scripts/run_model_router_benchmark_capture.py`
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_model_router_benchmark_capture.py`
  - Operator runbook updated with capture flow:
    - `/Users/eduardbelskih/Проекты Github/statproject/docs/OPERATOR_RUNBOOK.md`
  - Nightly benchmark workflow supports optional live capture (`workflow_dispatch.capture_run=true`) before snapshot:
    - `/Users/eduardbelskih/Проекты Github/statproject/.github/workflows/nightly-model-router-benchmark.yml`
  - Latest benchmark snapshot now has non-zero real coverage:
    - `/Users/eduardbelskih/Проекты Github/statproject/release/model_router_benchmark_report.json` (`runs_total=3`, `variants_total=15`, focused recommendations split across `minimax_single` / `gemini_single` / `routerai_combo`)

### Post-Baseline Hardening — LLM JSON Resilience (2026-03-02)

- Status: **Done**
- Done evidence:
  - Robust JSON extraction and local syntax repair in planner/critic parse path:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/llm/__init__.py`
  - New regression tests for malformed JSON recovery and single-pass plan recovery:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_llm_json_parsing.py`
  - Provider compatibility tests remain green:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_llm_providers.py`

### Post-Baseline Hardening — Benchmark Capture Visibility (2026-03-02)

- Status: **Done**
- Done evidence:
  - Snapshot endpoint now returns normalized `capture_last` block (status, run/dataset IDs, recommendation, capture coverage):
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/api/v2.py`
  - API regression covers capture summary contract:
    - `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_api_v2.py`
  - Copilot historical benchmark panel now renders live-capture status/details:
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/CopilotPage.jsx`
  - Frontend regression verifies live-capture rendering:
    - `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/features/copilot/CopilotPage.test.jsx`

## What Is Left To Call It “Production Baseline”

- Completed in this phase:
  - Changelog created: `/Users/eduardbelskih/Проекты Github/statproject/CHANGELOG.md`
  - Release notes created: `/Users/eduardbelskih/Проекты Github/statproject/release/RELEASE_NOTES_2026-03-01.md`
  - Operator runbook published: `/Users/eduardbelskih/Проекты Github/statproject/docs/OPERATOR_RUNBOOK.md`
  - Production smoke report generated with `overall_status: PASS`:
    - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_2026-03-01.md`
    - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_220356.md`
    - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_230435.md`
    - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_231154.md`
    - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_20260301_231352.md`
- Release formalization completed:
  - Git tag published: `prod-baseline-2026-03-01`
  - GitHub release published: `Production Baseline 2026-03-01`
  - Release URL: `https://github.com/EdBels69/statproject/releases/tag/prod-baseline-2026-03-01`

## Next Phase

- Phase 2 roadmap (JASP-parity to expert-grade pipeline) is tracked in:
  - `/Users/eduardbelskih/Проекты Github/statproject/docs/PHASE2_JASP_PARITY_PLAN_2026-03-02.md`
