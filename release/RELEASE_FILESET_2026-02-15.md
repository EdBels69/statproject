# StatProject Release Fileset (2026-02-15)

This manifest isolates deploy-relevant changes from the current dirty worktree.

## Artifacts
- Runtime include list: `release/release_runtime_files.txt`
- Runtime deletions list: `release/release_runtime_deletions.txt`
- QA/support list (tests/docs/scripts): `release/release_qa_files.txt`
- Full status snapshot: `release/manifest_status.tsv`
- Runtime archive candidate: `release/statproject_release_candidate_2026-02-15.tar.gz`
- Runtime archive checksum: `release/statproject_release_candidate_2026-02-15.tar.gz.sha256`

## Counts
- Runtime files to deploy: 90
- Runtime deletions to apply: 26
- QA/support files: 67

## Inclusion logic (runtime)
- Included: changed/new files under:
  - `backend/app/**`
  - `frontend/src/**` (excluding `*.test.*`)
  - `backend/requirements.txt`
  - `backend/.env.example`
  - `backend/artifacts/openapi.json`
  - `frontend/package.json`, `frontend/package-lock.json`
  - `app/api/routes/sorcerer.py`
  - Win11 deploy files (`deploy-win11.ps1`, `stop-win11.ps1`, `restart-win11.ps1`, `*.bat`, `DEPLOYMENT_WIN11.md`)
- Excluded from runtime set:
  - tests, docs, prompt templates
  - temporary artifacts (`backend/temp_*`, `workspace/datasets/**`, `frontend/test-results/**`)
  - backups (`_backups/**`)
  - ad-hoc files (`copilot_sessions.json`, `backend/backend/output/**`, etc.)

## Deploy notes
1. Use `release/statproject_release_candidate_2026-02-15.tar.gz` as the source bundle.
2. Apply deletions listed in `release/release_runtime_deletions.txt` on target if deploying over an existing tree.
3. If deploying from a clean checkout/image build, deletions are naturally enforced by absence.
