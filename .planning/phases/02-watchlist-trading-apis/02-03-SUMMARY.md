---
phase: 02-watchlist-trading-apis
plan: 03
subsystem: api
tags: [fastapi, sqlite, pydantic, portfolio, trading]

# Dependency graph
requires:
  - phase: 02-watchlist-trading-apis
    provides: "app.trade_engine.apply_trade (pure buy/sell math, plan 02-02) and app.watchlist router pattern (plan 02-01)"
provides:
  - "GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history"
  - "compute_and_record_snapshot(conn, price_cache) shared helper for plan 02-04's background snapshot task"
affects: [02-04-background-snapshot-task, phase-3-ai-chat-trade-path]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service layer takes sqlite3.Connection + PriceCache directly (no FastAPI dependency) so it is unit-testable and reusable outside the HTTP router"
    - "Single-commit transaction per trade: cash update + position upsert/delete + trade insert + snapshot insert, one conn.commit() at the end; TradeError raised before any write short-circuits with zero DB mutation"

key-files:
  created: [backend/app/portfolio.py, backend/tests/test_portfolio.py]
  modified: [backend/app/main.py]

key-decisions:
  - "Missing cache price for a held position falls back to valuing at avg_cost (unrealized_pnl=0 for that position) rather than raising, so total_value stays finite -- documented in build_portfolio's docstring"
  - "A trade request for a ticker with no cached price at all is rejected as a TradeError (400), since a trade cannot fill at an unknown price -- this differs from valuation's avg_cost fallback, which only applies to already-held positions being displayed"
  - "compute_and_record_snapshot does not commit -- callers control the transaction boundary, letting execute_trade fold it into the trade's single commit and letting plan 02-04's periodic task commit on its own cadence"

patterns-established:
  - "Trade math delegated entirely to app.trade_engine.apply_trade; portfolio.py never reimplements buy/sell arithmetic"

requirements-completed: [PORT-01, PORT-02, PORT-03, PORT-05, PORT-06]

coverage:
  - id: D1
    description: "GET /api/portfolio returns cash_balance, positions[] (quantity, avg_cost, current_price, unrealized_pnl, pct_change), total_value, total_unrealized_pnl"
    requirement: "PORT-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_get_portfolio_fresh_db"
        status: pass
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_buy_fills_at_cached_price_and_updates_cash"
        status: pass
    human_judgment: false
  - id: D2
    description: "POST /api/portfolio/trade fills instantly at the cached price, updates cash/positions with correct weighted average cost, supports fractional shares, and logs a trade row"
    requirement: "PORT-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_second_buy_computes_weighted_average_cost"
        status: pass
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_fractional_buy_updates_cash_and_position_exactly"
        status: pass
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_sell_all_shares_removes_position_and_increases_cash"
        status: pass
    human_judgment: false
  - id: D3
    description: "Insufficient cash / insufficient shares trades return HTTP 400 with a clear message and leave cash/positions unchanged"
    requirement: "PORT-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_buy_insufficient_cash_rejected_and_unchanged"
        status: pass
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_sell_insufficient_shares_rejected_and_unchanged"
        status: pass
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_sell_more_than_held_after_partial_position_rejected_and_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every successful trade writes an immediate portfolio_snapshots row (immediate half of PORT-06)"
    requirement: "PORT-06"
    verification:
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_immediate_snapshot_recorded_after_successful_trade"
        status: pass
    human_judgment: false
  - id: D5
    description: "GET /api/portfolio/history returns portfolio_snapshots ordered by recorded_at"
    requirement: "PORT-05"
    verification:
      - kind: integration
        ref: "backend/tests/test_portfolio.py::TestPortfolio::test_history_ordered_by_recorded_at"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-04
status: complete
---

# Phase 2 Plan 3: Portfolio & Trading API Summary

**REST API for portfolio valuation and market-order trading, built on the pure `app.trade_engine.apply_trade`, with a single-transaction trade path and a shared immediate-snapshot helper for reuse by the upcoming background snapshot task.**

## Performance

- **Duration:** 25 min
- **Tasks:** 3 (portfolio service layer, router + main.py registration, TestClient coverage) — plan grouped Task 1 and Task 2 into a single service+router file
- **Files modified:** 3 (1 created: `portfolio.py`, 1 created: `test_portfolio.py`, 1 modified: `main.py`)

## Accomplishments
- `build_portfolio` computes cash, per-position valuation (current_price, unrealized_pnl, pct_change), total_value, and total_unrealized_pnl, reading prices only from the injected `PriceCache`
- `execute_trade` delegates all buy/sell math to `app.trade_engine.apply_trade`, persists cash/position/trade/snapshot atomically in one transaction, and never writes on rejection
- `compute_and_record_snapshot(conn, price_cache)` extracted as a caller-commits helper, ready for reuse by plan 02-04's periodic background task
- Router exposes `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`, registered in `create_app()` before the static mount
- 12 TestClient tests cover fresh state, weighted average cost across repeat buys, fractional shares, full-sell position removal, both PORT-03 rejection cases with before/after unchanged-state assertions, Pydantic quantity validation, missing-price rejection, immediate snapshot, and history ordering

## Task Commits

1. **Task 1 + Task 2: Portfolio service layer + trade/history router** - `3166323` (feat)
2. **Task 3: TestClient tests for portfolio + trading** - `75be28f` (test)

_Note: Tasks 1 and 2 both targeted the new `backend/app/portfolio.py` file; since the plan built the service layer and router together in one file, they were committed as a single `feat` commit rather than two artificial partial-file commits._

## Files Created/Modified
- `backend/app/portfolio.py` - Service layer (`read_cash`, `read_positions`, `build_portfolio`, `compute_and_record_snapshot`, `execute_trade`) + Pydantic models + `create_portfolio_router()` factory
- `backend/app/main.py` - Imports and registers `create_portfolio_router()` after the watchlist router, before the static mount
- `backend/tests/test_portfolio.py` - 12 TestClient tests using the `db_path`/`client` fixture pattern from `test_watchlist.py`

## Decisions Made
- Valuation of a held position with no cache price falls back to `avg_cost` (documented in `build_portfolio`'s docstring) so `total_value` stays finite; a *trade* against a ticker with no cache price at all is rejected outright since there is no price to fill at
- `compute_and_record_snapshot` intentionally does not commit, so `execute_trade` can fold it into the trade's single commit while plan 02-04's periodic task can commit on its own schedule
- Used `INSERT ... ON CONFLICT(user_id, ticker) DO UPDATE` for the position upsert to match the schema's `UNIQUE(user_id, ticker)` constraint cleanly in one statement

## Deviations from Plan

None - plan executed exactly as written. Tasks 1 and 2 target the same new file (`portfolio.py`), so they were authored and committed together as noted above; this is a commit-grouping choice, not a scope deviation — every acceptance criterion from both tasks is met (service layer functions exist and are unit-testable; router is registered before the static mount).

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `compute_and_record_snapshot(conn, price_cache)` is exported from `app.portfolio` and ready for plan 02-04's background 30s snapshot task to import directly
- `execute_trade` is the single validated trade path (DB + pure math) that Phase 3's AI chat can reuse for LLM-initiated trades
- All 129 backend tests pass (`uv run --extra dev pytest`); ruff clean on all touched files

---
*Phase: 02-watchlist-trading-apis*
*Completed: 2026-07-04*

## Self-Check: PASSED

- FOUND: backend/app/portfolio.py
- FOUND: backend/tests/test_portfolio.py
- FOUND: main.py registration of create_portfolio_router
- FOUND commit: 3166323
- FOUND commit: 75be28f
