# Runbook: prod-candidate-2026-02-22

## Quick start

```bash
./deploy_preflight.sh
BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build
curl http://localhost:8200/health
```

## Default ports

- Backend: `8100`
- Frontend: `3100`

## If ports are busy

```bash
BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build
```

## Stop

```bash
docker compose down
```

## Core docs

- `docs/PRODUCTION_GO_LIVE_CHECKLIST_2026-02-22.md`
- `docs/RELEASE_READINESS_2026-02-22.md`
- `DEPLOYMENT.md`
