# Changelog

All notable changes to this project are documented in this file.

## [2026-03-01] Production Baseline Hardening

### Added

- Operator runbook with backup/restore and incident playbook:
  - `/Users/eduardbelskih/Проекты Github/statproject/docs/OPERATOR_RUNBOOK.md`
- Operational scripts:
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/ops_backup_workspace.sh`
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/ops_restore_workspace.sh`
  - `/Users/eduardbelskih/Проекты Github/statproject/scripts/release_production_smoke.sh`
- DoD tests:
  - Reflection strategy-switch scenario in `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_agent_orchestrator.py`
  - Release bundle coverage for lineage + DOCX artifact in `/Users/eduardbelskih/Проекты Github/statproject/backend/tests/test_release_bundle.py`
  - Frontend monolith size guard in `/Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/pageSizeGuard.test.js`

### Verified

- Backend suite: `385 passed, 8 skipped`.
- Frontend lint/tests/build: all pass.
- COVID release bundle strict compare smoke: pass.
