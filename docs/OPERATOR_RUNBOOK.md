# Operator Runbook

Date: 2026-03-01  
Scope: Docker deployment of StatProject on Linux/macOS (Windows notes at the end).

## 1. Service Topology

- Frontend container: `frontend` (port `3000`)
- Backend container: `backend` (port `8000`)
- Persistent dataset storage: Docker volume `backend_data` (actual name: `<compose_project>_backend_data`)

Reference: `/Users/eduardbelskih/Проекты Github/statproject/docker-compose.yml`

## 2. Daily Health Checklist

Run from repo root:

```bash
./status-statproject.command
docker compose ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/docs >/dev/null
```

If any command fails, go to Incident Playbook (section 6).

## 3. Safe Operations Rule

Before any stop/restart that may remove volumes, always create backup:

```bash
./scripts/ops_backup_workspace.sh
```

Default backup path: `~/statproject_backups`.

Important:
- `/Users/eduardbelskih/Проекты Github/statproject/stop.sh` executes `docker compose down -v` and removes persistent volume data.

## 4. Backup and Restore

### 4.1 Backup

```bash
./scripts/ops_backup_workspace.sh
```

Optional custom directory:

```bash
./scripts/ops_backup_workspace.sh /absolute/path/to/backups
```

### 4.2 Restore

1. Stop running services:

```bash
docker compose down
```

2. Restore from archive:

```bash
./scripts/ops_restore_workspace.sh /absolute/path/to/statproject_workspace_YYYYmmdd_HHMMSS.tar.gz --yes
```

3. Start services:

```bash
./start-statproject.command
```

4. Verify:

```bash
curl -fsS http://localhost:8000/health
```

## 5. Release Cutover Checklist

1. Run production smoke gate:

```bash
./scripts/release_production_smoke.sh
```

Optional strict benchmark gate:

```bash
BENCHMARK_MIN_RUNS=10 BENCHMARK_STRICT=1 ./scripts/release_production_smoke.sh
```

2. Verify report `release/PRODUCTION_SMOKE_*.md` has `overall_status: PASS`.
3. Ensure smoke report contains benchmark steps with `status: PASS`:
   - `Model-router benchmark snapshot build`
   - `Backend benchmark contract tests`
4. Create or update release notes (`CHANGELOG.md`).
5. Create git tag for release candidate or production release.
6. Keep one fresh workspace backup before rollout window.

## 6. Incident Playbook

### Incident A: Backend unhealthy

Symptoms:
- `/health` non-200
- frontend cannot fetch API

Actions:

```bash
docker compose logs --tail=200 backend
docker compose restart backend
curl -fsS http://localhost:8000/health
```

If still failing:
- run `./scripts/release_production_smoke.sh` for diagnostic signal.
- rollback to previous image/tag if available.

### Incident B: Frontend shows API errors

Actions:

```bash
docker compose logs --tail=200 frontend
docker compose ps
curl -fsS http://localhost:8000/health
docker compose restart frontend
```

### Incident C: Data loss after volume reset

Actions:

```bash
docker compose down
./scripts/ops_restore_workspace.sh /absolute/path/to/latest-backup.tar.gz --yes
./start-statproject.command
```

### Incident D: Report export blocked by verifier gate

Symptoms:
- protocol report/export returns validation error.

Actions:

```bash
docker compose logs --tail=200 backend
```

Then inspect run artifacts (`verification.json`, `reflection_log.json`) and re-run corrected protocol.

## 7. Recovery Targets

- RPO target: last successful backup.
- RTO target (local environment): under 30 minutes with verified backup.

## 8. Model Router Benchmark Operations

Use this contour to compare LLM routing quality on accumulated real runs.

1. Capture one real benchmark run (optional, but recommended before snapshot if `runs_total=0`):

```bash
python3 backend/scripts/run_model_router_benchmark_capture.py \
  --workspace-dir workspace \
  --analysis-mode focused \
  --max-protocol-steps 1 \
  --allow-empty \
  --min-runs 10 \
  --pretty
```

Outputs:
- `release/model_router_benchmark_capture_last.json`
- run artifact `workspace/datasets/<dataset_id>/analysis/<run_id>/artifacts/llm_benchmark.json`

2. Build snapshot artifacts (JSON + Markdown):

```bash
python3 backend/scripts/benchmark_model_router.py \
  --workspace-dir workspace \
  --output release/model_router_benchmark_report.json \
  --markdown-out release/model_router_benchmark_report.md \
  --min-runs 10 \
  --pretty
```

3. Read current backend snapshot endpoint:

```bash
curl -fsS "http://localhost:8000/api/v1/v2/analysis/benchmark/model-router?min_runs=10&include_markdown=true&top_n=10"
```

4. Coverage gate policy:
- `coverage_gate.meets_threshold=true` means enough runs were collected for stable ranking.
- `coverage_gate.meets_threshold=false` means ranking is informational only and requires more benchmark runs.

For GitHub Actions (`Nightly Model Router Benchmark`) manual run:
- set `min_runs` input to target coverage threshold;
- enable `strict_coverage=true` to fail the job when threshold is not met.
- enable `capture_run=true` to run live capture before snapshot (requires configured LLM API secrets; safely skips when workspace has no eligible datasets).

5. Canonical outputs:
- `release/model_router_benchmark_report.json`
- `release/model_router_benchmark_report.md`

## 9. Windows Notes

Use PowerShell wrappers:

```powershell
.\deploy-win11.ps1
.\stop-win11.ps1
.\restart-win11.ps1
```

Primary reference: `/Users/eduardbelskih/Проекты Github/statproject/DEPLOYMENT_WIN11.md`.
