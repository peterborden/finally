---
phase: 02-watchlist-trading-apis
plan: 01
subsystem: api
tags: [fastapi, sqlite, pydantic, watchlist]

# Dependency graph
requires:
  - phase: 01-platform-foundation
    provides: "FastAPI app factory (app.state.price_cache, app.state.market_source via lifespan), SQLite schema + connection helper, MarketDataSource interface"
provides:
  - "GET/POST/DELETE /api/watchlist REST endpoints"
  - "create_watchlist_router() factory pattern for router registration"
affects: [03-ai-chat, 04-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Router factory reads app.state.price_cache / app.state.market_source per-request via the Request object (not captured at factory time), since market_source is only set once the lifespan has run"
    - "Ticker normalization (strip + upper-case) via a Pydantic field_validator, applied consistently to POST body and DELETE path param"

key-files:
  created:
    - backend/app/watchlist.py
    - backend/tests/test_watchlist.py
  modified:
    - backend/app/main.py

key-decisions:
  - "GET returns price=None (not a 404/error) for watchlist tickers with no cache entry yet, keeping the endpoint resilient to a slow-starting or failed market source"
  - "POST/DELETE degrade gracefully (log a warning, still mutate the DB) when app.state.market_source is None, matching Phase 1's existing failure-tolerant lifespan"

patterns-established:
  - "Ticker normalization at the API boundary (strip/upper-case) so client input variance never leaks into the UNIQUE(user_id,ticker) constraint or the market source's ticker set"

requirements-completed: [WATCH-01, WATCH-02, WATCH-03]

coverage:
  - id: D1
    description: "GET /api/watchlist returns every watched ticker joined with its latest cached price"
    requirement: "WATCH-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_get_returns_default_tickers"
        status: pass
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_get_reflects_seeded_cache_price"
        status: pass
    human_judgment: false
  - id: D2
    description: "POST /api/watchlist adds a ticker to the DB, normalizes/dedupes it, and starts it streaming via market_source.add_ticker"
    requirement: "WATCH-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_post_new_ticker_normalizes_and_dedupes"
        status: pass
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_post_calls_market_source_add_ticker"
        status: pass
    human_judgment: false
  - id: D3
    description: "DELETE /api/watchlist/{ticker} removes the ticker from the DB (idempotently) and stops it streaming via market_source.remove_ticker"
    requirement: "WATCH-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_delete_removes_ticker_and_is_idempotent"
        status: pass
      - kind: unit
        ref: "backend/tests/test_watchlist.py::TestWatchlist::test_delete_calls_market_source_remove_ticker"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-04
status: complete
---

# Phase 2 Plan 1: Watchlist API Summary

**GET/POST/DELETE /api/watchlist REST endpoints reading live prices from the shared PriceCache and wiring add/remove to the running MarketDataSource, with normalized/deduped tickers.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-04T00:00:00Z (approx.)
- **Completed:** 2026-07-04
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created router, 1 created test file, 1 modified — main.py registration)

## Accomplishments
- `backend/app/watchlist.py`: `create_watchlist_router()` factory exposing GET/POST /api/watchlist and DELETE /api/watchlist/{ticker}, all reading `request.app.state.price_cache` and `request.app.state.market_source` (never a data source directly)
- Ticker normalization (strip + upper-case) applied via Pydantic `field_validator` on POST and manually on the DELETE path param, so `"aapl "` and `"AAPL"` collide on the `UNIQUE(user_id, ticker)` constraint
- POST dedupes via `INSERT OR IGNORE`; DELETE is idempotent (200 with `removed: bool`, never 404)
- Router registered in `create_app()` before the static mount so `/api/*` is never shadowed
- 6 new TestClient tests in `backend/tests/test_watchlist.py` covering GET/POST/DELETE end-to-end, cache-price join (including the no-cache-entry `price=None` case), normalize/dedupe, and market-source wiring

## Task Commits

Each task was committed atomically:

1. **Task 1: Watchlist router module (GET / POST / DELETE)** - `c705c95` (feat)
2. **Task 2: Register the router in create_app and add TestClient coverage** - `b01a1c0` (feat)

## Files Created/Modified
- `backend/app/watchlist.py` - Router factory, Pydantic request/response models, ticker normalization, parameterized SQL for all three endpoints
- `backend/app/main.py` - `app.include_router(create_watchlist_router())` added alongside the existing SSE router registration
- `backend/tests/test_watchlist.py` - 6 TestClient tests reusing the `db_path`/`client` fixture pattern from `test_main.py`

## Decisions Made
- The plan's suggested test ("a ticker with no cache entry returns price=None") can't be exercised with any of the 10 default tickers under a real running `TestClient`, because `SimulatorDataSource.start()` synchronously seeds the cache for every startup ticker before the first request even arrives. Adjusted the test to insert an extra ticker (`ZZZZ`) directly into the DB via `get_connection()` (bypassing `market_source.add_ticker`), which has no cache entry and correctly returns `price=None`. This is a test-implementation detail only — the plan's endpoint behavior (`_build_entry` returns nulls when `cache.get(ticker)` is `None`) was already implemented as specified.
- No architectural deviations; app.state.market_source wiring already existed in Phase 1's `main.py` lifespan exactly as the plan described, so no additional wiring was needed.

## Deviations from Plan

None - plan executed as written (see "Decisions Made" above for a minor test-strategy adjustment, not a behavior change).

## Issues Encountered
- Initial test assumed a never-yet-simulated default ticker (GOOGL) would have `price=None`, but the simulator seeds all startup tickers immediately in `start()`. Resolved by testing the no-cache-entry path with a ticker added directly to the DB instead of through the market source (see Decisions Made).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Watchlist API is ready for the frontend (Phase 4) and AI chat (Phase 3) to drive add/remove/list through `/api/watchlist`.
- Parallel plan 02-02 (trade engine) landed concurrently with no file overlap; full backend suite (117 tests) passes including both plans' new tests.
- No blockers.

---
*Phase: 02-watchlist-trading-apis*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: backend/app/watchlist.py
- FOUND: backend/tests/test_watchlist.py
- FOUND: main.py registration (create_watchlist_router include_router call)
- FOUND commit: c705c95
- FOUND commit: b01a1c0
