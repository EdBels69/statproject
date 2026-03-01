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

- Full backend suite: `385 passed, 8 skipped`.
- Frontend: lint + unit tests + build pass.
- Production smoke report:
  - `/Users/eduardbelskih/Проекты Github/statproject/release/PRODUCTION_SMOKE_2026-03-01.md`
  - result: `overall_status: PASS`.

## Remaining Formal Action

- Create git tag and publish release entry using this note and:
  - `/Users/eduardbelskih/Проекты Github/statproject/CHANGELOG.md`.
