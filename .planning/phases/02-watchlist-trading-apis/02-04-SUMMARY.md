---
phase: 02-watchlist-trading-apis
plan: 04
subsystem: api
tags: [fastapi, asyncio, sqlite, background-task]

requires:
  - phase: 02-watchlist-trading-apis
    provides: "app.portfolio.compute_and_record_snapshot(conn, price_cache) from plan 02-03, and the _build_lifespan closure in app.main"
provides:
  - "SnapshotRecorder background asyncio task that records a portfolio_snapshots row every SNAPSHOT_INTERVAL_SECONDS (default 30s)"
  - "Lifespan wiring in app.main that starts/stops the recorder alongside the market data source"
  - "Test coverage proving periodic snapshots accumulate without a trade, and that shutdown cancels cleanly"
affects: [phase-04-frontend-pnl-chart]

tech-stack:
  added: []
  patterns:
    - "Background asyncio task lifecycle (start/stop, cancel+await, sleep-then-work loop) mirrored from app.market.simulator.SimulatorDataSource"
    - "Env-driven interval with defensive fallback to a safe default on missing/invalid/non-positive values"

key-files:
  created:
    - backend/app/snapshots.py
    - backend/tests/test_snapshots.py
  modified:
    - backend/app/main.py

key-decisions:
  - "The recorder loop sleeps before its first tick (not work-then-sleep like SimulatorDataSource) so it never races the DB's lazy first-request initialization; this was required to fix a regression it introduced in test_main.py::test_db_created_on_first_request"
  - "Snapshot task start/stop in the lifespan is guarded independently of the market source's start/stop, so a failure in one never blocks or breaks cleanup of the other"

requirements-completed: [PORT-06]

coverage:
  - id: D1
    description: "Background asyncio task records a portfolio_snapshots row every SNAPSHOT_INTERVAL_SECONDS (default 30s), configurable via env for fast tests"
    requirement: "PORT-06"
    verification:
      - kind: unit
        ref: "backend/tests/test_snapshots.py#test_periodic_snapshots_accumulate_without_a_trade"
        status: pass
      - kind: unit
        ref: "backend/tests/test_snapshots.py#test_invalid_interval_falls_back_to_default"
        status: pass
    human_judgment: false
  - id: D2
    description: "The task is started in the app lifespan and cancelled/awaited cleanly on shutdown, matching the market source task pattern"
    requirement: "PORT-06"
    verification:
      - kind: unit
        ref: "backend/tests/test_snapshots.py#test_periodic_snapshots_accumulate_without_a_trade (TestClient context exit raises nothing)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-04
status: complete
---

# Phase 2 Plan 4: Periodic Portfolio Snapshot Task Summary

**Background asyncio task records a portfolio_snapshots row every 30s (configurable), started/cancelled in the app lifespan, reusing the shared compute_and_record_snapshot helper**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-04T23:00:00Z (approx.)
- **Completed:** 2026-07-05T03:02:00Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- `SnapshotRecorder` in `backend/app/snapshots.py`: an asyncio task with a `start(price_cache)` / `stop()` lifecycle mirroring `SimulatorDataSource`, sleeping `SNAPSHOT_INTERVAL_SECONDS` (default 30, env-configurable with a defensive fallback) between ticks and calling the existing `portfolio.compute_and_record_snapshot(conn, price_cache)` on a fresh, closed-per-tick connection
- Wired into `app.main._build_lifespan`: started after the market data source, handle stored on `app.state.snapshot_task`, stopped in the `finally` block independently of market-source cleanup
- `backend/tests/test_snapshots.py`: drives the recorder at a 0.05s interval and proves snapshots accumulate over time with **no trade**, proving the periodic half of PORT-06 independent of the immediate post-trade half (already covered in `test_portfolio.py`); also proves clean shutdown and the env-var fallback behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Background snapshot task runner** - `630227f` (feat)
2. **Task 2: Wire the task into the lifespan + test at a short interval** - `8c21bc8` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `backend/app/snapshots.py` - `SnapshotRecorder` class: env-driven interval resolution (`_resolve_interval`), `start()`/`stop()` asyncio task lifecycle, per-tick try/except around a fresh `get_connection`/`compute_and_record_snapshot`/`commit`/`close` cycle
- `backend/app/main.py` - `_build_lifespan`: initializes `app.state.snapshot_task = None`, starts a `SnapshotRecorder` after the market source starts (guarded by try/except), stops it in `finally` before the market source (guarded independently)
- `backend/tests/test_snapshots.py` - Integration test driving the recorder via `TestClient` at a fast interval, plus a unit test for `_resolve_interval`'s fallback behavior

## Decisions Made
- **Sleep-first loop order (deviation from the literal simulator mirror):** the plan's read_first pointed at `SimulatorDataSource._run_loop`, which does work-then-sleep. Mirroring that literally made the recorder's very first tick fire immediately at lifespan startup, before any HTTP request had lazily initialized the database — this both raced/masked the DB-creation contract and, worse, caused `get_connection` to create an *empty* `finally.db` file before the first request, breaking `test_main.py::test_db_created_on_first_request` (which asserts the DB file does not exist until the first request). Switched to sleep-then-work so the recorder's first tick only fires after a full interval, giving the app time to serve at least one request first. Documented in the code as a comment referencing `app.main`'s `ensure_database` middleware.
- Snapshot task start/stop guarded with its own try/except in the lifespan (not sharing the market source's try/except), so a snapshot-start or snapshot-stop failure can never prevent the market source from starting/stopping or vice versa.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed loop ordering to avoid racing DB lazy-init**
- **Found during:** Task 2, running the full test suite (`uv run --extra dev pytest`)
- **Issue:** With the recorder using work-then-sleep (mirroring `SimulatorDataSource._run_loop` literally), the first snapshot tick fired at lifespan startup, before the first HTTP request had lazily created the SQLite schema via `app.main`'s `ensure_database` middleware. This raised `sqlite3.OperationalError: no such table: users_profile` on that first tick (caught and logged, non-fatal) but also caused `get_connection` to create an empty `finally.db` file as a side effect, which broke the pre-existing `test_main.py::test_db_created_on_first_request` assertion that the DB file does not exist before the first request.
- **Fix:** Swapped the loop to sleep first, then record. The recorder's first tick now only fires after a full `SNAPSHOT_INTERVAL_SECONDS` interval, by which point normal app usage (or the test's own health-check request) has already initialized the DB.
- **Files modified:** `backend/app/snapshots.py`, `backend/tests/test_snapshots.py` (updated a stale comment)
- **Verification:** Full suite (`uv run --extra dev pytest`) — 131/131 passed, including the previously-broken `test_main.py::test_db_created_on_first_request`
- **Committed in:** `8c21bc8` (Task 2 commit — the fix landed before the task's own commit, so the committed code already reflects sleep-first)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correctness fix to avoid corrupting a pre-existing test's fixed contract (DB file must not exist before the first request). No scope creep — same files, same task.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PORT-06 is now fully complete (immediate half from plan 02-03, periodic half from this plan) — `portfolio_snapshots` accumulates both on trade and every 30s in production
- Phase 4's P&L-over-time chart can rely on `GET /api/portfolio/history` returning a steadily growing time series even with no user activity
- No blockers

---
*Phase: 02-watchlist-trading-apis*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: backend/app/snapshots.py
- FOUND: backend/tests/test_snapshots.py
- FOUND: backend/app/main.py
- FOUND: .planning/phases/02-watchlist-trading-apis/02-04-SUMMARY.md
- FOUND commit: 630227f
- FOUND commit: 8c21bc8
