---
phase: 05-packaging-e2e-delivery
plan: 01
subsystem: infra
tags: [docker, uv, next-export, sqlite, packaging]

# Dependency graph
requires:
  - phase: 01-platform-foundation
    provides: SQLite schema, env-driven FINALLY_DB_PATH connection helper (backend/app/db/connection.py)
  - phase: 04-frontend-terminal-ui
    provides: Next.js static export (frontend/, output:'export' → frontend/out) served by FastAPI
provides:
  - Repo-root multi-stage Dockerfile (node:20-slim build + python:3.12-slim runtime) producing a single image
  - .dockerignore excluding build caches, local DBs, .git/.planning, and .env secrets from the build context
  - db/.gitkeep so the runtime volume-mount directory exists in a fresh clone
  - Verified: docker build succeeds, /api/health returns ok, / serves the real terminal UI, /app/db/finally.db persists across container restart on a named volume
affects: [05-02-start-stop-scripts, 05-03-e2e-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Multi-stage Docker build: frontend static export built in a node:20-slim stage, copied into a python:3.12-slim runtime stage — single image, single port (8000)"
    - "uv installed by copying the official ghcr.io/astral-sh/uv binary (no curl|sh); `uv sync --frozen --no-dev` installs locked runtime deps only"
    - "Env-driven wiring: FRONTEND_DIST and FINALLY_DB_PATH set in the image so app.main and db.connection resolve the copied static export and the volume-mounted SQLite path without code changes"

key-files:
  created: [Dockerfile, .dockerignore, db/.gitkeep]
  modified: []

key-decisions:
  - "Backend layout: copied backend/app into /app/app while pyproject.toml/uv.lock/README.md live at /app root, keeping `app.main` importable from the uv-managed /app working directory"
  - "Copied backend/README.md alongside pyproject.toml/uv.lock in the dependency layer — hatchling validates the declared readme file exists even during `uv sync --frozen` (deviation, see below)"
  - "HEALTHCHECK uses a python urllib one-liner instead of curl, since curl is not guaranteed present on python:3.12-slim"

patterns-established:
  - "Docker layer ordering: dependency manifests (package.json+lock / pyproject.toml+uv.lock+README) copied and installed before source, so source-only edits don't invalidate the dependency install layer"

requirements-completed: [PKG-01, PKG-02]

coverage:
  - id: D1
    description: "Single multi-stage Docker image builds the Next.js static export and runs FastAPI serving both /api/* and static assets on port 8000"
    requirement: "PKG-01"
    verification:
      - kind: manual_procedural
        ref: "docker build -t finally . (succeeded); curl -fsS http://localhost:8000/api/health returned {\"status\":\"ok\"}; curl -fsS http://localhost:8000/ contained _next/static bundle references (real export, not the Phase-1 placeholder)"
        status: pass
    human_judgment: false
  - id: D2
    description: "SQLite data at /app/db/finally.db persists across a container stop+start when /app/db is a named Docker volume"
    requirement: "PKG-02"
    verification:
      - kind: manual_procedural
        ref: "docker run with -v finally-verify-data:/app/db, hit /api/portfolio to trigger lazy DB init, docker exec test -f /app/db/finally.db, docker stop && docker start, re-verified file present and /api/health ok"
        status: pass
    human_judgment: false
  - id: D3
    description: "No secrets, local DB, or .planning content baked into the built image"
    verification:
      - kind: manual_procedural
        ref: "docker export finally-inspect | tar -tvf - | grep -E '\\.env$|\\.env\\.|\\.planning|finally\\.db$' (excluding .env.example) returned no matches"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-05
status: complete
---

# Phase 5 Plan 1: Docker Packaging Summary

**Repo-root multi-stage Dockerfile (Node 20 frontend build + Python 3.12/uv runtime) producing a single verified image that serves the real terminal UI and API on port 8000 with SQLite persisting via an /app/db volume mount.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3/3 completed
- **Files modified:** 3 (Dockerfile, .dockerignore, db/.gitkeep)

## Accomplishments
- Multi-stage Dockerfile: Stage 1 (`node:20-slim`) runs `npm ci` + `npm run build` to produce the Next.js static export (`frontend/out`); Stage 2 (`python:3.12-slim`) installs the uv binary from the official ghcr image, runs `uv sync --frozen --no-dev` against the locked backend dependencies, copies the backend source and the built static export, and launches `uvicorn app.main:app` on `0.0.0.0:8000`
- `.dockerignore` keeps the build context lean and secret-free: excludes `node_modules`, `.next`/`out`, `.venv`/`__pycache__`, local `*.db`/`*.sqlite3` files, `.git`, `.planning`, and `.env*` (while still allowing `.env.example`)
- `db/.gitkeep` ensures the `/app/db` volume-mount target directory exists in a fresh clone
- End-to-end verification: `docker build -t finally .` succeeds (image size 584MB); the running container answers `/api/health` with `{"status":"ok"}`, serves the real exported terminal UI at `/` (confirmed via `_next/static` bundle references, absence of the Phase-1 placeholder marker), creates `/app/db/finally.db` on first stateful request, and that file survives a `docker stop` + `docker start` cycle on a named volume
- Confirmed no `.env`, local database, or `.planning` content leaked into the built image via `docker export | tar -tvf`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add .dockerignore and db/.gitkeep** - `3bc2157` (chore)
2. **Task 2: Author the multi-stage Dockerfile** - `18011a4` (feat)
3. **Task 3: Build the image and verify serving + volume persistence** - `b368324` (fix — README.md copy fix found during verification; see Deviations)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `Dockerfile` - Multi-stage build: node:20-slim frontend export → python:3.12-slim runtime with uv-managed deps, FRONTEND_DIST/FINALLY_DB_PATH env wiring, HEALTHCHECK, and the uvicorn CMD
- `.dockerignore` - Excludes build artifacts, caches, local DBs, secrets, and .git/.planning from the build context
- `db/.gitkeep` - Ensures the runtime volume-mount directory exists in a fresh clone

## Decisions Made
- Backend copy layout: `backend/app` → `/app/app`, with `pyproject.toml`/`uv.lock`/`README.md` at `/app` root, so `app.main` imports resolve from the uv-managed working directory and `uvicorn app.main:app` runs without a separate `--app-dir` flag
- uv installed via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` rather than a curl|sh pipe, per the plan's supply-chain guidance
- HEALTHCHECK implemented with a `python -c "urllib.request.urlopen(...)"` one-liner since `curl` is not installed on the `python:3.12-slim` base and adding it would bloat the runtime image unnecessarily

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Copied backend/README.md into the dependency layer**
- **Found during:** Task 3 (`docker build -t finally .`)
- **Issue:** `backend/pyproject.toml` declares `readme = "README.md"`. The plan's Task 2 action copied only `backend/pyproject.toml` and `backend/uv.lock` before `uv sync --frozen --no-dev`. Because `uv sync` builds/installs the local project itself (hatchling `build_editable`), hatchling validated the declared readme file at build time and failed with `OSError: Readme file does not exist: README.md` since the file wasn't yet present in that layer.
- **Fix:** Added `backend/README.md` to the same `COPY` instruction as `pyproject.toml`/`uv.lock`, before `uv sync --frozen --no-dev` runs. This preserves the intended dependency-layer caching (README changes rarely, same cadence as pyproject.toml).
- **Files modified:** `Dockerfile`
- **Verification:** Re-ran `docker build -t finally .` — completed successfully end to end (frontend build, uv sync, image export).
- **Committed in:** `b368324` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary correctness fix to make the build succeed as specified; no scope creep, no architectural change.

## Issues Encountered
None beyond the auto-fixed Task 3 deviation above.

## User Setup Required
None - no external service configuration required. Docker was already available and running (v29.1.3, Docker Desktop 4.56.0).

## Next Phase Readiness
- The `finally` image is buildable and verified locally; Plan 05-02 (start/stop scripts) and Plan 05-03 (E2E tests) can both build on this Dockerfile and its env-var contract (`FRONTEND_DIST`, `FINALLY_DB_PATH`, port 8000, `/app/db` volume mount) without further changes.
- Test artifacts (`finally-verify` container, `finally-verify-data` volume) were removed after verification; only the `finally:latest` image remains locally.
- No blockers for subsequent Phase 5 plans.

---
*Phase: 05-packaging-e2e-delivery*
*Completed: 2026-07-05*

## Self-Check: PASSED

- FOUND: Dockerfile
- FOUND: .dockerignore
- FOUND: db/.gitkeep
- FOUND: 3bc2157 (Task 1 commit)
- FOUND: 18011a4 (Task 2 commit)
- FOUND: b368324 (Task 3 commit)
