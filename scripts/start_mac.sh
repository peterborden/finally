#!/usr/bin/env bash
#
# FinAlly — start script (macOS / Linux). Idempotent.
#
# Builds the Docker image if it does not exist yet (or when --build / --no-cache
# is passed), then (re)starts the container with the persistent data volume,
# port mapping, and .env file. Prints the URL and can open a browser.
#
# Usage:
#   scripts/start_mac.sh              # build if needed, run, print URL
#   scripts/start_mac.sh --build      # force a rebuild
#   scripts/start_mac.sh --no-cache   # force a rebuild with no layer cache
#   scripts/start_mac.sh --open       # open the browser once it's up
#
set -euo pipefail

# --- config ------------------------------------------------------------------
IMAGE_NAME="finally:latest"
CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"
HOST_PORT="8000"
CONTAINER_PORT="8000"
URL="http://localhost:${HOST_PORT}"

# Resolve project root (parent of this script's dir) so the script works from
# anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# --- args --------------------------------------------------------------------
FORCE_BUILD=0
NO_CACHE=0
OPEN_BROWSER=0
for arg in "$@"; do
  case "${arg}" in
    --build)    FORCE_BUILD=1 ;;
    --no-cache) FORCE_BUILD=1; NO_CACHE=1 ;;
    --open)     OPEN_BROWSER=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: ${arg}" >&2; exit 2 ;;
  esac
done

# --- preflight ---------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Error: the Docker daemon is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

# --- build (if needed) -------------------------------------------------------
IMAGE_EXISTS=0
if docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  IMAGE_EXISTS=1
fi

if [[ "${FORCE_BUILD}" -eq 1 || "${IMAGE_EXISTS}" -eq 0 ]]; then
  echo "==> Building image ${IMAGE_NAME} ..."
  BUILD_ARGS=()
  [[ "${NO_CACHE}" -eq 1 ]] && BUILD_ARGS+=(--no-cache)
  docker build ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} -t "${IMAGE_NAME}" .
else
  echo "==> Image ${IMAGE_NAME} already exists (use --build to rebuild)."
fi

# --- env file ----------------------------------------------------------------
ENV_ARGS=()
if [[ -f .env ]]; then
  ENV_ARGS+=(--env-file .env)
  echo "==> Using .env"
else
  echo "==> No .env found — running with defaults (simulator market data, no LLM key)."
  echo "    Copy .env.example to .env and add OPENROUTER_API_KEY for AI chat."
fi

# --- (re)start container -----------------------------------------------------
# Idempotent: remove any existing container (running or stopped) with this name.
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "==> Removing existing container ${CONTAINER_NAME} ..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

echo "==> Starting ${CONTAINER_NAME} ..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  -v "${VOLUME_NAME}:/app/db" \
  ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} \
  --restart unless-stopped \
  "${IMAGE_NAME}" >/dev/null

echo ""
echo "  FinAlly is starting at ${URL}"
echo "  Logs:  docker logs -f ${CONTAINER_NAME}"
echo "  Stop:  scripts/stop_mac.sh"
echo ""

if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  if command -v open >/dev/null 2>&1; then
    open "${URL}"            # macOS
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}"        # Linux
  fi
fi
