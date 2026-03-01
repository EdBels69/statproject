#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "${ROOT_DIR}")}"
VOLUME_NAME="${VOLUME_NAME:-${PROJECT_NAME}_backend_data}"
OUT_DIR="${1:-${HOME}/statproject_backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="statproject_workspace_${STAMP}.tar.gz"
ARCHIVE_PATH="${OUT_DIR}/${ARCHIVE_NAME}"

mkdir -p "${OUT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not reachable. Start Docker Desktop / dockerd and retry." >&2
  exit 1
fi

if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
  candidate="$(docker volume ls --format '{{.Name}}' | grep '_backend_data$' | head -n 1 || true)"
  if [[ -n "${candidate}" ]]; then
    VOLUME_NAME="${candidate}"
  else
    echo "Docker volume not found: ${VOLUME_NAME}" >&2
    echo "Hint: set COMPOSE_PROJECT_NAME or VOLUME_NAME if your compose project name differs." >&2
    exit 1
  fi
fi

docker run --rm \
  -v "${VOLUME_NAME}:/volume:ro" \
  -v "${OUT_DIR}:/backup" \
  alpine:3.20 \
  sh -lc "cd /volume && tar czf '/backup/${ARCHIVE_NAME}' ."

echo "Backup created: ${ARCHIVE_PATH}"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${ARCHIVE_PATH}" | awk '{print "sha256: " $1}'
fi
