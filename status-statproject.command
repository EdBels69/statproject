#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "Container status:"
docker compose ps
echo ""

echo -n "Backend health: "
curl -sS -o /tmp/statproject_health.json -w "%{http_code}" "http://localhost:8000/health" || true
echo ""
if [ -f /tmp/statproject_health.json ]; then
  cat /tmp/statproject_health.json
  echo ""
fi
