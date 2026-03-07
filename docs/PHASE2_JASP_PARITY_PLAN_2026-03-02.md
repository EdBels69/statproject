# Phase 2 Plan (2026-03-02): JASP-Parity to Expert-Grade Pipeline

## 0) Current baseline (verified)

- Iterations 1-6 from global plan are completed.
- Post-baseline hardening is completed: chronology quality, live benchmark capture, LLM JSON resilience, capture visibility.
- Full regression at handoff: backend `402 passed, 8 skipped`; frontend `42 passed`.

Source references:
- `/Users/eduardbelskih/Проекты Github/statproject/docs/MASTER_PLAN_STATUS_2026-03-01.md`
- `/Users/eduardbelskih/Проекты Github/statproject/backend/app/stats/method_coverage.py`

## 1) Phase 2 objective

Bring StatProject from "broad method coverage" to "JASP-class analyst UX":

- stronger method families (especially Bayesian, survival, reliability, longitudinal, time-series);
- deterministic method selection rationale in every run;
- report coherence (design -> descriptive -> assumptions -> inferential -> multiplicity -> interpretation);
- reproducible release artifacts for every execution path;
- benchmarked model-router policy with live capture and rollback-safe presets.

## 2) Iteration 7: Methodic Depth + Canonical Contracts (1-2 weeks)

### Scope

- Close functional/contract gaps for already-declared advanced methods:
  - `ancova`, `pca`, `efa`, `kmeans`, `hierarchical_clustering`, `time_series_analysis`, `bland_altman`, Bayesian family.
- Freeze per-method output contracts (required fields, diagnostics, effect-size payloads, plotting payload schema).
- Align `METHOD_COVERAGE_MATRIX.md` with `method_coverage.py` (remove stale matrix drift).

### Deliverables

- Method contract registry (single source of truth): required keys per method + validator.
- Golden fixtures for each advanced method in execute-v2.
- Strict compatibility matrix documentation synced with runtime coverage.

### Definition of Done

- Every advanced method has contract test: positive + malformed payload negative.
- Execute-v2 returns normalized method payload even under degraded conditions (warnings, not silent shape breaks).
- `docs/METHOD_COVERAGE_MATRIX.md` matches `backend/app/stats/method_coverage.py` exactly.

### Test gate

- `python3 -m pytest -q backend/tests/test_engine_advanced_methods_dispatch.py`
- `python3 -m pytest -q backend/tests/test_execute_v2_advanced_coverage.py`
- `python3 -m pytest -q backend/tests/test_protocol_validator.py`

## 3) Iteration 8: Bayesian + Longitudinal + Survival Expansion (2-3 weeks)

### Scope

- Extend from current Bayesian core to analyst-ready families:
  - Bayesian repeated/paired workflows with prior metadata and sensitivity traces.
  - Posterior diagnostics in result payload (convergence/precision indicators where applicable).
- Add missing high-impact clinical methods:
  - Cox proportional hazards (`cox_regression`) with assumption diagnostics.
  - GLMM/GEE for clustered binary/count outcomes.
  - Poisson/Negative Binomial for count endpoints.
- Add protocol-level guards for design-method mismatch.

### Deliverables

- New method handlers + method coverage map + aliases + validator rules.
- Report renderers for new methods in HTML/DOCX/PDF with interpretation templates.
- Copilot planner prompts upgraded to explain why Bayesian/survival method is selected.

### Definition of Done

- End-to-end run for each new family from plan -> execute -> report -> release bundle.
- Verifier blocks invalid survival/count outputs the same way as classic p/CI checks.
- No regression in existing mixed-effects/survival_km workflows.

### Test gate

- New tests: `test_engine_survival_extended.py`, `test_engine_glmm_gee.py`, `test_engine_count_models.py`, `test_reporting_survival_models.py`.
- Existing suites remain green: full backend regression.

## 4) Iteration 9: Report Semantics + Traceable Interpretation (1-2 weeks)

### Scope

- Resolve report quality gaps raised in expert review:
  - no jargon-only correction labels;
  - explicit hypotheses and subgroup definitions;
  - explicit dataset/source and analysis set provenance;
  - hard link between descriptive stats and each inferential step.
- Enforce chronology sanity for time-series and reject absurd time scales unless explicitly allowed.
- Add interpretation confidence/risk notes (assumption violations, low power, sparse groups).

### Deliverables

- Report graph model: section-level links between hypothesis -> tests -> tables/figures -> conclusions.
- Provenance panel in report header and release manifest extension.
- Policy for terminology rendering (human labels first, raw code optional in appendix).

### Definition of Done

- For each inference block report includes: H0/H1, chosen test rationale, key numbers, correction used, interpretation.
- Time-series section requires valid time index quality mark; otherwise downgraded/skipped with explanation.
- Russian localization parity for PDF/HTML report blocks restored and covered by regression.

### Test gate

- `python3 -m pytest -q backend/tests/test_reporting_design_quality.py`
- `python3 -m pytest -q backend/tests/test_reporting_batch_tables.py`
- `python3 -m pytest -q backend/tests/test_report_quality_checklist.py`

## 5) Iteration 10: Reliability + Production Controls + E2E Corpus (1-2 weeks)

### Scope

- Expand production controls:
  - benchmark policy presets with rollback (`conservative`, `balanced`, `latency-first`).
  - deterministic replay checks for release bundle re-execution.
  - dataset quality score thresholds by analysis mode.
- Build E2E corpus (dirty Excel + clinical longitudinal + agreement + time-series + survival).
- Add release readiness checklist automation.

### Deliverables

- `release_readiness` command/report with hard gates.
- Benchmark policy registry and UI switch with audit trail.
- E2E corpus pack with expected outputs and tolerances.

### Definition of Done

- One-command smoke: ingest -> design -> plan -> execute -> report -> release -> replay compare.
- Benchmark policy switch changes recommendation deterministically and is recorded in artifacts.
- Production checklist produces PASS/FAIL with actionable reasons.

### Test gate

- `scripts/release_production_smoke.sh` (strict mode)
- new `backend/tests/test_release_readiness.py`
- full backend + frontend regression

## 6) Cross-iteration constraints

- No removal of existing working scenarios.
- Every new method must include:
  - protocol validator rules,
  - verifier rules,
  - report renderer mapping,
  - release artifact compatibility,
  - unit + integration tests.
- Any change to method semantics requires update in:
  - `/Users/eduardbelskih/Проекты Github/statproject/backend/app/stats/method_coverage.py`
  - `/Users/eduardbelskih/Проекты Github/statproject/docs/METHOD_COVERAGE_MATRIX.md`

## 7) Immediate next execution step

Start Iteration 7 with two concrete tasks:

1. Implement method contract registry for advanced families and wire it into execute-v2 response normalization.
2. Sync and regenerate `METHOD_COVERAGE_MATRIX.md` directly from `method_coverage.py` (no manual drift).

