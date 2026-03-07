#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "Starting StatProject..."

# Ensure Docker Desktop app is launched.
open -a Docker >/dev/null 2>&1 || true

echo "Waiting for Docker engine..."
ready=0
for _ in {1..90}; do
  if docker info >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "Docker engine is not ready. Open Docker Desktop and retry."
  exit 1
fi

# Build only if local images are absent.
if ! docker image inspect statproject-backend:latest >/dev/null 2>&1 || \
   ! docker image inspect statproject-frontend:latest >/dev/null 2>&1; then
  echo "Building images (first run)..."
  docker compose up -d --build
else
  docker compose up -d --no-build
fi

echo "StatProject is running."
echo "Frontend:    http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API docs:    http://localhost:8000/docs"

open "http://localhost:3000" >/dev/null 2>&1 || true
