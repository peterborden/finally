#!/usr/bin/env bash
# Idempotent one-command launcher for FinAlly on macOS/Linux.
#
# Usage:
#   scripts/start_mac.sh          # build only if the "finally" image is missing
#   scripts/start_mac.sh --build  # force a rebuild of the "finally" image
#
# Safe to re-run: if the "finally" container is already running, this prints
# the URL and exits 0 without creating a duplicate container.
set -euo pipefail

IMAGE_NAME="finally"
CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"
PORT=8000
URL="http://localhost:${PORT}"

# Resolve the repo root relative to this script's location so it can be run
# from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

FORCE_BUILD=false
if [[ "${1:-}" == "--build" ]]; then
  FORCE_BUILD=true
fi

# First-time convenience: create .env from the template if it's missing.
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit it to add OPENROUTER_API_KEY / MASSIVE_API_KEY, or leave blank / set LLM_MOCK=true to run without keys."
fi

# If the container is already running, this is a no-op — print the URL and exit.
if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "FinAlly is already running at ${URL}"
  exit 0
fi

# Build the image only if it's missing, or if the user forced a rebuild.
if [[ "${FORCE_BUILD}" == "true" ]]; then
  echo "Building ${IMAGE_NAME} image (--build requested)..."
  docker build -t "${IMAGE_NAME}" .
elif ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Building ${IMAGE_NAME} image (no existing image found)..."
  docker build -t "${IMAGE_NAME}" .
else
  echo "Reusing existing ${IMAGE_NAME} image (pass --build to force a rebuild)."
fi

# Remove a stopped container with the same name so we can start fresh.
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  docker rm "${CONTAINER_NAME}" >/dev/null
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:${PORT}" \
  -v finally-data:/app/db \
  --env-file .env \
  "${IMAGE_NAME}"

echo "FinAlly is starting at ${URL}"

# Best-effort browser open on macOS; never fail if `open` is unavailable (e.g. Linux).
if command -v open >/dev/null 2>&1; then
  open "${URL}" >/dev/null 2>&1 || true
fi
