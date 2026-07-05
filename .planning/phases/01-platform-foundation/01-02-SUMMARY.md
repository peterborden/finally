---
phase: 01-platform-foundation
plan: 02
subsystem: api
tags: [fastapi, uvicorn, sse, sqlite, httpx, testclient]

requires:
  - phase: 01-platform-foundation
    provides: "app.db package (init_database, get_db_path, get_connection, DEFAULT_TICKERS, DEFAULT_CASH) from Plan 01-01"
provides:
  - "create_app() FastAPI factory: lifespan-managed market data source + SSE router, /api/health, lazy DB-init middleware, static frontend mount"
  - "Module-level app object (uvicorn app.main:app) and python -m app entry point"
  - "app.state.price_cache / app.state.market_source contract for future portfolio/watchlist endpoints"
  - "Placeholder static/index.html served at / until the Phase 4 Next.js export lands"
affects: [02-portfolio, 03-watchlist, 04-frontend, chat]

tech-stack:
  added: ["httpx>=0.27.0 (dev-only, TestClient dependency)"]
  patterns:
    - "App factory pattern (create_app()) with a closure-bound lifespan so the same PriceCache instance is shared between route registration and startup/shutdown"
    - "API routes and SSE router registered before StaticFiles is mounted at '/' so /api/* always wins over the static catch-all"
    - "One-shot request-scoped lazy init: an app.state boolean flag gates the http middleware's init_database() call so it runs its full idempotency check only once per process"
    - "FRONTEND_DIST / FINALLY_DB_PATH env vars control served directory and DB path, defaulting to backend/app/static and db/finally.db respectively"

key-files:
  created:
    - backend/app/main.py
    - backend/app/__main__.py
    - backend/app/static/index.html
    - backend/tests/test_main.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "PriceCache is created once in create_app() (not inside the lifespan coroutine) and threaded through both app.include_router(create_stream_router(cache)) and the lifespan closure via _build_lifespan(cache), so the SSE router and the market data source always share the exact same cache instance."
  - "SSE precedence/content-type is tested by monkeypatching starlette.requests.Request.is_disconnected to return True, rather than by issuing a real streaming HTTP call through TestClient — see Deviations."
  - "Market source start failures are caught and logged rather than raised, so a market data problem never prevents /api/health, static serving, or the DB middleware from working (per the plan's threat-model disposition T-01-APP-03: accept)."

requirements-completed: [APP-01, APP-02, APP-03, DB-01]

coverage:
  - id: D1
    description: "create_app() lifespan starts the market data source with the 10 default tickers and mounts the SSE router; GET /api/stream/prices is live"
    requirement: "APP-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_main.py#TestApp::test_sse_route_registered"
        status: pass
      - kind: manual_procedural
        ref: "curl -N http://localhost:8123/api/stream/prices (manual boot verification, streamed live GBM prices)"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/health returns 200 with a healthy status body suitable for a Docker healthcheck"
    requirement: "APP-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_main.py#TestApp::test_health"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET / serves the placeholder index.html from the static frontend directory (FRONTEND_DIST-overridable)"
    requirement: "APP-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_main.py#TestApp::test_root_serves_placeholder"
        status: pass
    human_judgment: false
  - id: D4
    description: "The first HTTP request lazily creates db/finally.db with six tables, a $10k profile, and 10 default watchlist tickers"
    requirement: "DB-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_main.py#TestApp::test_db_created_on_first_request"
        status: pass
    human_judgment: false
  - id: D5
    description: "/api/* routes always resolve to the API, never to the static catch-all (route registration order enforced)"
    verification:
      - kind: unit
        ref: "backend/tests/test_main.py#TestApp::test_sse_route_registered"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-07-04
status: complete
---

# Phase 1 Plan 2: FastAPI Application Assembly Summary

**Bootable `create_app()` FastAPI factory wiring the existing market subsystem (SSE + GBM simulator) into a lifespan, a Docker-ready `/api/health` check, lazy SQLite init via middleware, and static placeholder serving — all behind an `/api/*`-before-static route precedence guarantee.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-04T22:16:30Z
- **Completed:** 2026-07-04T22:51:00Z
- **Tasks:** 2 (plus 1 pre-approved checkpoint)
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments
- `backend/app/main.py`: `create_app()` factory — closure-bound lifespan starts `create_market_data_source(cache)` with the 10 `SEED_PRICES` tickers, mounts `create_stream_router(cache)`, stores `price_cache`/`market_source` on `app.state`, and stops the source on shutdown (failures logged, never fatal).
- `GET /api/health` returns `{"status": "ok"}`, registered before the static mount.
- `ensure_database` HTTP middleware calls `init_database(get_db_path())` once per process (guarded by an `app.state` flag), satisfying DB-01's "create on first request".
- `StaticFiles` mounted at `/` last (env `FRONTEND_DIST`, default `backend/app/static`), so `/api/*` and `/api/stream/*` always take precedence over the catch-all.
- `backend/app/static/index.html`: dark placeholder page with the spec's color palette and a `finally-placeholder-marker` id for test assertions.
- `backend/app/__main__.py`: `python -m app` runs `uvicorn.run("app.main:app", host="0.0.0.0", port=8000)`.
- `backend/tests/test_main.py`: 4-test `TestApp` class (health, static placeholder, SSE route precedence + content-type, lazy DB creation + seed) using `TestClient(create_app())` with `FINALLY_DB_PATH` pointed at an isolated `tmp_path`.
- Added `httpx>=0.27.0` to the `dev` extra (approved dependency, encode org, dev-only) and ran `uv sync --extra dev`.

## Task Commits

Each task was committed atomically:

1. **Checkpoint: httpx package legitimacy** - pre-approved by the user in the execution prompt; no separate commit (folded into Task 2's commit).
2. **Task 1: create_app() — lifespan, health, static, DB middleware** - `67a140e` (feat)
3. **Task 2: TestClient suite — health, static, SSE precedence, lazy DB** - `78c024d` (test)

**Plan metadata:** _pending — recorded after final docs commit_

## Files Created/Modified
- `backend/app/main.py` - `create_app()`, `_build_lifespan()`, `_resolve_frontend_dir()`, module-level `app`
- `backend/app/__main__.py` - `python -m app` entry point (`uvicorn.run`)
- `backend/app/static/index.html` - Placeholder dark-theme page with test marker
- `backend/tests/test_main.py` - `TestApp`: health, static, SSE precedence, lazy DB init
- `backend/pyproject.toml` - Added `httpx>=0.27.0` to `[project.optional-dependencies].dev`
- `backend/uv.lock` - Regenerated lockfile (httpx + httpcore added)

## Decisions Made
- Built the `PriceCache` once in `create_app()` and passed the same instance into both `create_stream_router()` and a lifespan closure (`_build_lifespan(cache)`), rather than creating a second cache inside the lifespan coroutine — this was caught and fixed during implementation before it ever shipped (see Deviations, Rule 1).
- Kept the market-source start/stop wrapped in try/except with `logger.exception()` per the plan's threat-model disposition (T-01-APP-03: accept, DoS low severity) — a simulator hiccup never wedges `/api/health` or static serving.
- `FRONTEND_DIST` directory is created (`mkdir(parents=True, exist_ok=True)`) at app-factory time so `StaticFiles` never raises at import/boot if the directory is momentarily absent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two separate PriceCache instances would have been created (router vs. lifespan)**
- **Found during:** Task 1, first draft of `main.py`
- **Issue:** Initial implementation created a `PriceCache()` inside the lifespan coroutine and a second, separate `PriceCache()` for `create_stream_router()` in `create_app()` — the SSE stream would have read from a cache the market source never wrote to, so no prices would ever appear over SSE.
- **Fix:** Refactored to build one `PriceCache` in `create_app()`, store it on `app.state.price_cache`, pass it to `create_stream_router(cache)`, and thread the same instance into the lifespan via a `_build_lifespan(cache)` closure factory.
- **Files modified:** `backend/app/main.py`
- **Verification:** Manual boot test (`uv run uvicorn app.main:app`) confirmed `curl -N /api/stream/prices` streams real GBM price updates.
- **Committed in:** `67a140e` (Task 1 commit — caught before the first commit, not a follow-up fix)

**2. [Rule 3 - Blocking] Starlette TestClient cannot execute an infinite-generator streaming request via `.stream()`**
- **Found during:** Task 2, writing `test_sse_route_registered`
- **Issue:** The plan's suggested approach (`with client.stream("GET", "/api/stream/prices") as response: ...`) hung indefinitely. Investigation of `starlette/testclient.py::_TestClientTransport.handle_request` showed Starlette's synchronous `TestClient` drives the *entire* ASGI call to completion inside a blocking portal call before returning any response to httpx — it does not support partial/incremental reads of an in-progress stream. Since `GET /api/stream/prices` is an intentionally infinite generator (per PLAN.md §6, only terminates on client disconnect), and disconnect-detection itself depends on the response completing first, the two conditions deadlock (confirmed identically with `httpx.AsyncClient(transport=httpx.ASGITransport(...))`, which has the same full-drain behavior). This is a general limitation of both HTTP test transports against truly infinite SSE bodies, not a flaw in `app/market/stream.py`.
- **Fix:** In `test_sse_route_registered`, monkeypatched `starlette.requests.Request.is_disconnected` to return `True` immediately. The generator (`_generate_events` in `app/market/stream.py`, unmodified) yields `"retry: 1000\n\n"` first, then checks `is_disconnected()` on its very next loop iteration — with the patch, it exits after that single check, letting the real production endpoint run to completion deterministically in under a second while still exercising genuine route resolution, status code, and `content-type` header via the actual `TestClient`.
- **Files modified:** `backend/tests/test_main.py`
- **Verification:** `uv run --extra dev pytest tests/test_main.py -q` — 4/4 pass in 0.36s (no hang); full suite `uv run --extra dev pytest -q` — 82/82 pass in ~1s.
- **Committed in:** `78c024d` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug caught pre-commit, 1 blocking test-infrastructure issue)
**Impact on plan:** Deviation 1 was a correctness bug that would have silently broken live price streaming (core product value) — caught before any commit. Deviation 2 is a test-technique fix only; `app/market/stream.py` was not modified and its production behavior (real client disconnect handling via `EventSource`/browser) is unaffected — only the *test harness's* ability to simulate disconnect against Starlette's non-streaming `TestClient` needed adjusting. No scope creep.

## Issues Encountered
Investigated why `client.stream()` hung by reading `starlette/testclient.py` and `httpx/_transports/asgi.py` source directly (both confirmed to fully drain the ASGI call before returning); resolved via the `is_disconnected` monkeypatch documented above rather than weakening the assertions or skipping the test.

## User Setup Required
None - no external service configuration required. `httpx` is a dev-only test dependency (TestClient's own documented requirement), already resolved via `uv sync --extra dev`.

## Next Phase Readiness
- `create_app()`, module-level `app`, and `python -m app` are all boot-verified: `uv run uvicorn app.main:app --port 8000` serves `/api/health`, `/`, and streams live prices at `/api/stream/prices`; the first request creates `db/finally.db` with the seeded schema.
- `app.state.price_cache` and `app.state.market_source` are the stable contract future phases (portfolio valuation, watchlist management) should use to read live prices or manage tracked tickers — no direct instantiation of `PriceCache`/`MarketDataSource` needed downstream.
- `FRONTEND_DIST` env var is ready for Phase 4 to point at the built Next.js static export directory; no code changes needed in `app/main.py` when that lands.
- No blockers for Phase 2.

---
*Phase: 01-platform-foundation*
*Completed: 2026-07-04*

## Self-Check: PASSED

All 4 created files confirmed present on disk (`backend/app/main.py`, `backend/app/__main__.py`, `backend/app/static/index.html`, `backend/tests/test_main.py`); both task commit hashes (67a140e, 78c024d) confirmed in git log; full backend suite (82 tests) green.
