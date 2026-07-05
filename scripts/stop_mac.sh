#!/usr/bin/env bash
# Idempotent stop script for FinAlly on macOS/Linux.
#
# Stops and removes the "finally" container but explicitly preserves the
# "finally-data" volume so portfolio/watchlist/trade data survives.
# Safe to re-run: exits 0 even if the container is already stopped/removed.
set -euo pipefail

CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "Stopped and removed the ${CONTAINER_NAME} container."
else
  echo "No ${CONTAINER_NAME} container found — nothing to stop."
fi

echo "Data preserved in the ${VOLUME_NAME} volume (not removed)."
