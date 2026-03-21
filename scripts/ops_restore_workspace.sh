#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  cat >&2 <<'USAGE'
Usage:
  ./scripts/ops_restore_workspace.sh /absolute/path/to/backup.tar.gz --yes

Notes:
  - This operation REPLACES current workspace data in Docker volume.
  - Stop running services before restore:
      docker compose down
USAGE
  exit 1
fi

BACKUP_PATH="$1"
CONFIRM_FLAG="$2"

if [[ "${CONFIRM_FLAG}" != "--yes" ]]; then
  echo "Restore aborted: second argument must be --yes" >&2
  exit 1
fi

if [[ ! -f "${BACKUP_PATH}" ]]; then
  echo "Backup archive not found: ${BACKUP_PATH}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not reachable. Start Docker Desktop / dockerd and retry." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "${ROOT_DIR}")}"
VOLUME_NAME="${VOLUME_NAME:-${PROJECT_NAME}_backend_data}"

if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
  echo "Docker volume not found, creating: ${VOLUME_NAME}"
  docker volume create "${VOLUME_NAME}" >/dev/null
fi

BACKUP_DIR="$(cd "$(dirname "${BACKUP_PATH}")" && pwd)"
BACKUP_FILE="$(basename "${BACKUP_PATH}")"

docker run --rm \
  -v "${VOLUME_NAME}:/volume" \
  -v "${BACKUP_DIR}:/backup:ro" \
  alpine:3.20 \
  sh -lc "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf '/backup/${BACKUP_FILE}' -C /volume"

echo "Restore completed into volume: ${VOLUME_NAME}"
echo "Source archive: ${BACKUP_PATH}"
