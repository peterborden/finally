# syntax=docker/dockerfile:1
#
# FinAlly — multi-stage build (PLAN §11).
#   Stage 1 (Node 20 slim):   build the Next.js static export  -> frontend/out
#   Stage 2 (Python 3.12 slim): uv sync backend from the committed lock,
#                               copy the frontend export into ./static,
#                               serve the FastAPI app on :8000.
#
# Build context is the PROJECT ROOT (see .dockerignore).
# Full end-to-end build requires BOTH frontend/ and backend/app/ to be complete;
# in an isolated DevOps worktree those may be partial — see planning/BUILD_LOG.md.

# ------------------------------------------------------------------------------
# Stage 1: build the frontend static export
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Install deps first for better layer caching. package-lock.json is optional
# (PLAN §11 specifies `npm install`); copy it if present.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Build the static export. Next.js with `output: 'export'` emits to ./out.
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: backend runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS backend

# uv: fast, reproducible installs from the committed lockfile.
# Pulled from the official distroless image (binaries at /uv and /uvx).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# uv configuration:
#   - install into a project venv at /app/.venv (default)
#   - copy (not hardlink) since build + runtime layers differ
#   - compile bytecode for faster cold starts
#   - never fetch a managed Python; use the slim image's 3.12
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# --- dependency layer (cached until pyproject/lock change) --------------------
# README.md is referenced by pyproject (readme = "README.md") and is needed
# for the project build step, so bring it in with the manifests.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- application layer -------------------------------------------------------
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Frontend static export -> backend/static (BUILD_CONTRACT §7: main.py mounts
# ./static as the SPA fallback AFTER all /api routes).
COPY --from=frontend-builder /frontend/out ./static

# Runtime config. FINALLY_DB_PATH points at the volume mount (PLAN §11 / §5).
ENV FINALLY_DB_PATH=/app/db/finally.db
RUN mkdir -p /app/db

EXPOSE 8000

# Health check hits GET /api/health (BUILD_CONTRACT §5.8). stdlib only — no curl
# in the slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else sys.exit(1)"

# create_app() is the ASGI factory (BUILD_CONTRACT §2). --factory tells uvicorn
# to call it. If Backend eng instead exports a module-level `app`, change this to
# `app.main:app` and drop --factory.
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
