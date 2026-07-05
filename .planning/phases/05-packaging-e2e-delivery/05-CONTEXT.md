# Phase 5: Packaging & E2E Delivery - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Package the whole app into a single one-command Docker container serving both API and the static frontend on port 8000, with persistent SQLite via a volume, idempotent start/stop scripts + .env.example, and a Playwright E2E suite under LLM_MOCK=true. Requirements: PKG-01, PKG-02, PKG-03, PKG-04.

</domain>

<canonical_refs>
## Canonical References

- `planning/PLAN.md` §11 (Docker & Deployment — multi-stage Dockerfile, volume, scripts), §12 (Testing Strategy — E2E scenarios), §3/§5 (single container, env vars).
- `backend/` — uv project (pyproject.toml, uv.lock). App entry: `app.main:app` (create_app). Serves static from `FRONTEND_DIST` (default backend/app/static placeholder). `GET /api/health` for healthcheck.
- `frontend/` — Next.js static export; `npm --prefix frontend run build` → `frontend/out`.
- Env vars (PLAN.md §5): `OPENROUTER_API_KEY` (required for real LLM), `MASSIVE_API_KEY` (optional real market data), `LLM_MOCK` (true → deterministic mock, used by E2E).
</canonical_refs>

<decisions>
## Implementation Decisions

### Claude's Discretion (guided by PLAN.md §11/§12)
- **Multi-stage Dockerfile** (repo root):
  - Stage 1 (Node 20-slim): copy `frontend/`, `npm ci`/`npm install` + `npm run build` → produces `frontend/out`.
  - Stage 2 (Python 3.12-slim): install uv, copy `backend/`, `uv sync --frozen` (from uv.lock), copy the built `frontend/out` into the image (e.g. `/app/frontend_dist`), set `FRONTEND_DIST` to it, expose 8000, CMD `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` (app-dir backend). Ensure the SQLite path defaults to `/app/db/finally.db` (FINALLY_DB_PATH) so the volume mount at `/app/db` persists it.
  - Add a `.dockerignore` (exclude node_modules, .next, .venv, __pycache__, db/*.db, .git, .planning).
- **Volume (PKG-02):** `db/finally.db` ↔ `/app/db`. Container writes to /app/db; a named volume or bind mount persists across restarts. Document the `docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally` invocation.
- **Scripts (PKG-03, idempotent):** `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1`. start = build image if needed (or `--build`), run container with volume + port + `--env-file .env`, print the URL, optionally open browser. stop = stop+remove container, KEEP the volume. All safe to re-run.
- **.env.example** at repo root: `OPENROUTER_API_KEY=`, `MASSIVE_API_KEY=`, `LLM_MOCK=false` with comments (per PLAN.md §5). Real `.env` stays gitignored (already denied to me).
- **E2E (PKG-04):** Playwright suite in `test/` with `docker-compose.test.yml` that runs the app container (with `LLM_MOCK=true`) + a Playwright runner. Cover the key scenarios (PLAN.md §12): fresh start shows default 10-ticker watchlist + $10k + streaming prices; add/remove a watchlist ticker; buy shares (cash down, position appears); sell shares; portfolio visualizations render (heatmap + P&L chart present); AI chat (mocked) sends a message, gets a response, and a mock-directive trade shows inline; SSE reconnect resilience. Keep tests deterministic under LLM_MOCK. A convenience `docker-compose.yml` (optional wrapper) may also be added.
- **Optional:** a top-level README section or update on how to run.

### Constraints
- One container, one port (8000), no CORS. Don't change app behavior — this phase is packaging + tests only. Keep the image lean (slim bases, no dev deps in runtime stage where avoidable, though uv's dev extra is fine if needed for nothing at runtime).

</decisions>

<code_context>
## Existing Code Insights

Backend serves static from FRONTEND_DIST (Phase 1). Frontend builds to frontend/out (Phase 4). App boots via `uv run uvicorn app.main:app` with `--app-dir backend`. LLM_MOCK=true makes /api/chat deterministic (Phase 3) — E2E relies on this. DB path is env-driven (FINALLY_DB_PATH default db/finally.db). Playwright is available via the plugin; the E2E suite should be runnable both in docker-compose.test.yml and ideally locally against a running container.

</code_context>

<specifics>
## Specific Ideas

Docker build context is the repo root (needs both frontend/ and backend/). Use BuildKit-friendly layer ordering (copy manifests + install before copying source for cache). Healthcheck can hit /api/health. The E2E compose should wait for health before running Playwright.

</specifics>

<deferred>
## Deferred Ideas

Cloud deployment (Terraform/App Runner) is v2/Out of Scope for this milestone.

</deferred>
