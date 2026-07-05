# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the Next.js static export (frontend/out)
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /build

# Install dependencies first so this layer caches across source-only changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy the rest of the frontend source and build the static export.
# next.config.mjs sets output:'export', producing /build/out.
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python runtime serving the API + the built static export
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Copy the official uv/uvx binaries rather than piping curl|sh.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install locked runtime dependencies first so this layer caches across
# backend source-only changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend source. The hatch wheel target packages ["app"], and
# pyproject.toml/uv.lock already live at /app, so copying backend/app here
# keeps `app.main` importable from /app.
COPY backend/app ./app

# Copy the frontend static export built in Stage 1.
COPY --from=frontend-build /build/out /app/frontend_dist

# Env wiring: point the app at the copied static export and the volume-mounted DB.
ENV FRONTEND_DIST=/app/frontend_dist
ENV FINALLY_DB_PATH=/app/db/finally.db

# Ensure the volume mount point exists even before the first write.
RUN mkdir -p /app/db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)"]

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
