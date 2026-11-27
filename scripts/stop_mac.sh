#!/usr/bin/env bash
#
# FinAlly — stop script (macOS / Linux). Idempotent.
#
# Stops and removes the running container. Does NOT remove the named data
# volume, so the SQLite database (portfolio, trades, chat) persists.
#
# Usage:
#   scripts/stop_mac.sh
#
set -euo pipefail

CONTAINER_NAME="finally"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "==> Stopping and removing container ${CONTAINER_NAME} ..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "==> Done. Data volume 'finally-data' preserved."
else
  echo "==> Container ${CONTAINER_NAME} is not present. Nothing to do."
fi
