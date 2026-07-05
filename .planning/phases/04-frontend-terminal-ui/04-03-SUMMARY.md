---
phase: 04-frontend-terminal-ui
plan: 03
subsystem: ui
tags: [nextjs, react, typescript, tailwind, sse, portfolio, trading]

requires:
  - phase: 04-01
    provides: Next.js static-export scaffold, lib/types.ts, lib/api.ts, lib/useLivePrices.ts
provides:
  - Header.tsx (live total value, cash balance, connection dot)
  - ConnectionDot.tsx (green/yellow/red SSE status indicator)
  - PositionsTable.tsx (six-column positions table, live-updated, sign-colored)
  - TradeBar.tsx (instant market order form, no confirmation dialog)
affects: [04-06 page assembly]

tech-stack:
  added: []
  patterns:
    - "Live-recompute pattern: components accept both the last-fetched REST snapshot AND the live PriceMap, and recompute derived values (total value, current price, P&L, % change) from the live price when available, falling back to the snapshot otherwise."

key-files:
  created:
    - frontend/components/ConnectionDot.tsx
    - frontend/components/Header.tsx
    - frontend/components/PositionsTable.tsx
    - frontend/components/TradeBar.tsx
  modified: []

key-decisions:
  - "Header/PositionsTable recompute derived values from useLivePrices' PriceMap on every render rather than only refreshing on portfolio re-fetch, matching the plan's requirement that totals 'tick with the SSE stream'."
  - "TradeBar has zero confirmation UI (no modal, no window.confirm) per the locked spec (T-04-06 accepted risk) — Buy/Sell call api.trade directly and surface the thrown Error.message inline on failure."

patterns-established:
  - "Prop-driven derived-value recomputation: pass both the fetched snapshot and the live SSE map into presentational components; let the component fall back through livePrice -> snapshot field -> avg_cost as needed."

requirements-completed: [UI-06, UI-07, UI-09]

coverage:
  - id: D1
    description: "Header shows wordmark, live total portfolio value, cash balance, and a connection-status dot mapping connected/reconnecting/connecting to green/yellow"
    requirement: "UI-09"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Visual color mapping and live-tick behavior require a human to confirm in the browser once 04-06 wires the page; typecheck only proves the code compiles and prop types line up."
  - id: D2
    description: "PositionsTable renders ticker/quantity/avg cost/current price/unrealized P&L/% change, recomputed from live prices and colored by sign, with pct_change x100 displayed as a percentage"
    requirement: "UI-06"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Correct sign coloring and live-recompute visual behavior need human verification in-browser after 04-06 assembly; no component-level unit tests exist yet for these presentational components."
  - id: D3
    description: "TradeBar fires an instant market order (ticker, quantity, Buy/Sell) with no confirmation dialog and surfaces backend error detail inline"
    requirement: "UI-07"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
      - kind: other
        ref: "grep -Li 'confirm(' frontend/components/TradeBar.tsx (no window.confirm/modal present)"
        status: pass
    human_judgment: true
    rationale: "End-to-end trade execution against the live backend (success fill + insufficient-cash error path) requires the running app; only static/typecheck verification was performed in this plan."

duration: 20min
completed: 2026-07-05
status: complete
---

# Phase 4 Plan 3: Header, ConnectionDot, PositionsTable, TradeBar Summary

**Portfolio-visibility and instant-trading surfaces: a live-ticking header/positions table driven by the SSE PriceMap, plus a no-confirmation TradeBar that posts directly to /api/portfolio/trade.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-05T03:27:00Z (approx)
- **Completed:** 2026-07-05T03:47:35Z
- **Tasks:** 2
- **Files modified:** 4 (all new)

## Accomplishments
- `ConnectionDot` maps `useLivePrices` status to green (connected) / yellow (connecting/reconnecting) / red (fallback) tokens with an accessible `role="status"` label.
- `Header` renders the FinAlly wordmark plus a live total portfolio value (cash + sum of quantity × live price, falling back through `current_price` then `avg_cost`) and cash balance, formatted as USD currency with tabular numerals.
- `PositionsTable` renders all six required columns (ticker, quantity, avg cost, current price, unrealized P&L, % change), preferring the live SSE price for current-price/P&L/% recomputation, rendering `pct_change * 100` with a `%` suffix, and coloring P&L/% change green/red by sign.
- `TradeBar` posts directly to `api.trade` with no confirmation dialog or modal, clears the quantity and shows an inline fill note on success, shows the backend's thrown `Error.message` (the `detail` string) inline on failure without clearing inputs, and disables both buttons while a request is in flight.

## Task Commits

Each task was committed atomically:

1. **Task 1: ConnectionDot + Header (live total value, cash, status dot)** - `92d238e` (feat)
2. **Task 2: PositionsTable + TradeBar (instant market orders)** - `73da37e` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `frontend/components/ConnectionDot.tsx` - Colored status dot + label from `ConnectionStatus`
- `frontend/components/Header.tsx` - Top bar: wordmark, live total value, cash, connection dot
- `frontend/components/PositionsTable.tsx` - Six-column positions table, live-recomputed, sign-colored
- `frontend/components/TradeBar.tsx` - Ticker/quantity form with instant Buy/Sell, no confirmation

## Decisions Made
- Live-recompute derived financial values (total value, current price, P&L, % change) directly in the presentational component from the `PriceMap` prop rather than waiting for a fresh `/api/portfolio` fetch, per 04-CONTEXT.md's "Total value in the header updates live from cache prices" and the plan's explicit acceptance criteria.
- `TradeBar` normalizes the ticker to uppercase before sending (matches backend `_normalize_ticker`), and treats any `Error` thrown by `lib/api.ts`'s `trade()` as the user-facing message verbatim (it is already the backend's `detail` string).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `Header`, `ConnectionDot`, `PositionsTable`, and `TradeBar` are ready to be imported and wired into `app/page.tsx` by plan 04-06, which owns fetching `/api/portfolio` and calling each component's props (`onTraded` should trigger a portfolio re-fetch).
- `npm --prefix frontend run typecheck` passes with these four files plus the concurrently-landed 04-02/04-04/04-05 components in the tree (verified after all four parallel plans' files were present).
- No blockers. Visual/interactive verification (color correctness, live ticking, actual trade fills) is deferred to 04-06's full-page checkpoint since these components aren't mounted anywhere until page assembly.

---
*Phase: 04-frontend-terminal-ui*
*Completed: 2026-07-05*

## Self-Check: PASSED

All 4 created files found on disk; both task commits (92d238e, 73da37e) found in git log.
