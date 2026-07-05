---
phase: 02-watchlist-trading-apis
plan: 02
subsystem: api
tags: [trading, portfolio, dataclasses, pytest, tdd]

# Dependency graph
requires:
  - phase: 01-platform-foundation
    provides: SQLite schema (positions, trades, portfolio_snapshots) and app conventions (frozen dataclasses, from __future__ import annotations)
provides:
  - Pure trade-math module (app/trade_engine.py) with apply_trade(), Position, TradeResult, Side, TradeError
affects: [02-03 (portfolio/trade HTTP endpoint), phase-3 (AI-driven trades)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-function core: trade math isolated from DB/HTTP so both the manual-trade endpoint and future AI chat share one validated implementation"
    - "Frozen dataclasses (slots=True) for Position and TradeResult, matching app/market/models.py style"
    - "TradeError exception (not a result-object union) for rejections, carrying a human-readable message the HTTP layer translates to 400"
    - "Epsilon-based sell-to-zero (QUANTITY_EPSILON = 1e-9) to avoid floating-point dust positions"

key-files:
  created:
    - backend/app/trade_engine.py
    - backend/tests/test_trade_engine.py
  modified: []

key-decisions:
  - "Rejections raise TradeError rather than returning a rejection object, matching Python idiom for validation failures and giving 02-03 a clean try/except -> HTTP 400 mapping"
  - "apply_trade takes keyword-only arguments (side, quantity, price, cash, position) to prevent positional-argument mix-ups between quantity/price/cash at call sites"

patterns-established:
  - "Pattern: pure trade-math core validated in isolation before I/O wiring — reused by both manual trade endpoint (02-03) and Phase 3 AI trade execution"

requirements-completed: [PORT-03, PORT-04]

coverage:
  - id: D1
    description: "Buy computes weighted average cost across fresh and existing positions, including fractional shares, and decrements cash by qty*price"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_trade_engine.py::TestBuy"
        status: pass
    human_judgment: false
  - id: D2
    description: "Sell increments cash, decrements quantity, preserves avg_cost, and flags remove_position when the resulting quantity is within epsilon of zero (including fractional partial sells)"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_trade_engine.py::TestSell"
        status: pass
    human_judgment: false
  - id: D3
    description: "Buy with insufficient cash and sell with insufficient shares are rejected via TradeError without producing any applied state; non-positive quantity/price also rejected"
    requirement: "PORT-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_trade_engine.py::TestSell::test_sell_with_no_position_is_rejected, TestBuy::test_buy_with_insufficient_cash_is_rejected_without_mutation, TestInvalidInput"
        status: pass
    human_judgment: false
  - id: D4
    description: "Module is pure (no sqlite3/fastapi/app.market imports) so it can be reused unmodified by the HTTP trade endpoint and Phase 3 AI chat"
    verification:
      - kind: other
        ref: "grep -nE \"import (sqlite3|fastapi)|from app.market\" backend/app/trade_engine.py (no matches)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-05
status: complete
---

# Phase 2 Plan 2: Pure Trade Engine Summary

**Pure buy/sell trade-math module (`app/trade_engine.py`) with weighted average-cost accounting, fractional shares, and epsilon-based sell-to-zero, validated by 29 unit tests covering every case in the plan's behavior spec.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-05T02:45:00Z
- **Completed:** 2026-07-05T03:00:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `apply_trade()` computes buy-side weighted average cost (`(old_qty*old_avg + qty*price)/(old_qty+qty)`), correctly handling fresh positions, blended existing positions, and fractional share quantities
- `apply_trade()` computes sell-side cash increment and quantity decrement, preserving `avg_cost`, and flags `remove_position=True` when the resulting quantity is within `QUANTITY_EPSILON` (1e-9) of zero — including a test with genuine floating-point residue (`0.1 + 0.2 - 0.3`)
- Insufficient-cash buys and insufficient-shares sells raise `TradeError` with a descriptive message (shortfall amount included) and leave the caller's `Position` input completely unmutated
- Non-positive quantity and non-positive price are rejected for both buy and sell before any math runs
- 29 unit tests pass; ruff clean; purity confirmed via grep (no `sqlite3`/`fastapi`/`app.market` imports)

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1 RED: failing tests for pure trade engine** - `64ec462` (test)
2. **Task 1 GREEN: implement pure trade engine** - `3b1acaf` (feat)

**Plan metadata:** (this commit, see below)

_Note: No REFACTOR commit was needed — the GREEN implementation required no follow-up cleanup._

## Files Created/Modified
- `backend/app/trade_engine.py` - Pure trade math: `Side` enum, `Position`/`TradeResult` frozen dataclasses, `TradeError`, `apply_trade()`, `QUANTITY_EPSILON`
- `backend/tests/test_trade_engine.py` - 29 tests across `TestBuy`, `TestSell`, `TestInvalidInput`, `TestPurity`

## Decisions Made
- Rejections use a raised `TradeError` exception rather than a returned rejection object/union type — simpler call-site ergonomics (`try/except TradeError`) for the 02-03 HTTP endpoint, which maps it directly to a 400 response with the exception's message.
- `apply_trade` uses keyword-only arguments to avoid positional mix-ups between `quantity`, `price`, and `cash` (all `float`) at call sites in the future endpoint and AI chat integration.
- Followed `app/market/models.py` conventions exactly: `from __future__ import annotations`, `@dataclass(frozen=True, slots=True)`, full type hints, module/class/function docstrings.

## Deviations from Plan

None - plan executed exactly as written. The plan gave Claude's discretion on exact type names; `Position`, `TradeResult`, `Side`, `TradeError`, `apply_trade` were chosen and used consistently.

## Issues Encountered
None. RED tests failed with the expected `ModuleNotFoundError` (module didn't exist yet); GREEN implementation passed all 29 tests on the first run.

## TDD Gate Compliance

Both gates present in git log for this plan, in order:
1. `test(02-02): add failing tests for pure trade engine` (`64ec462`) — RED
2. `feat(02-02): implement pure trade engine (buy/sell math + validation)` (`3b1acaf`) — GREEN

No REFACTOR commit — none needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `app/trade_engine.py` is ready to be imported by plan 02-03's `/api/portfolio/trade` endpoint: call `apply_trade(side=..., quantity=..., price=<from PriceCache>, cash=<from users_profile>, position=Position(quantity=..., avg_cost=...))`, catch `TradeError` for a 400 response, and persist the returned `TradeResult` fields (upsert/delete position per `remove_position`, update cash, append trade row, snapshot).
- No blockers. This plan touched only `backend/app/trade_engine.py` and `backend/tests/test_trade_engine.py`, staying clear of the parallel 02-01 work on `backend/app/main.py` and watchlist files.

## Self-Check: PASSED
- FOUND: backend/app/trade_engine.py
- FOUND: backend/tests/test_trade_engine.py
- FOUND commit: 64ec462 (test - RED)
- FOUND commit: 3b1acaf (feat - GREEN)
