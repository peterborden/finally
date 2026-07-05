---
phase: 04-frontend-terminal-ui
plan: 04
subsystem: ui
tags: [react, nextjs, recharts, lightweight-charts, treemap, typescript]

# Dependency graph
requires:
  - phase: 04-frontend-terminal-ui (04-01)
    provides: Next.js TS app scaffold, Tailwind theme tokens, lib/types.ts, lib/api.ts, lib/useLivePrices.ts
provides:
  - PortfolioHeatmap.tsx — recharts Treemap, one rect per position sized by weight, colored by P&L
  - PnLChart.tsx — lightweight-charts v5 line series of total portfolio value over time
affects: [04-06 (page assembly wires both components into the bottom band)]

# Tech tracking
tech-stack:
  added: []  # recharts + lightweight-charts already in package.json from 04-01 scaffold
  patterns:
    - "recharts Treemap custom content renderer: React.ReactElement passed to `content`, recharts clones it with TreemapNode props at render time"
    - "lightweight-charts v5 series creation via chart.addSeries(LineSeries, options) (v4 addLineSeries removed)"
    - "Chart components keep their DOM container ref always mounted; empty-state message renders as an absolutely-positioned overlay so late-arriving data doesn't require a second effect/ref wiring"

key-files:
  created:
    - frontend/components/PortfolioHeatmap.tsx
    - frontend/components/PnLChart.tsx
  modified: []

key-decisions:
  - "Heatmap weight = quantity x live SSE price (falls back to position.current_price when no live price yet) so the treemap re-sizes/re-colors without waiting for a full /api/portfolio re-fetch"
  - "Cell color opacity scaled by |pct_change| clamped at 20% so small moves aren't washed out and large moves don't over-saturate"
  - "PnLChart de-duplicates/nudges recorded_at timestamps that collide at whole-second resolution so lightweight-charts' strictly-ascending-time requirement is never violated"

patterns-established:
  - "Empty-state overlay pattern for imperative-DOM chart components (lightweight-charts): never conditionally unmount the ref container, only overlay a message, so a single mount-time effect keeps working across empty -> populated transitions"

requirements-completed: [UI-04, UI-05]

coverage:
  - id: D1
    description: "PortfolioHeatmap renders a recharts Treemap with one rectangle per position sized by weight and colored green/red by P&L, with an empty state"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Visual color/sizing correctness and empty-state rendering require eyeballing the rendered treemap; typecheck only proves the code compiles against the declared prop/data shapes."
  - id: D2
    description: "PnLChart renders a lightweight-charts line of total_value over recorded_at, updates on history change, and disposes on unmount"
    requirement: "UI-05"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Chart rendering, resize behavior, and unmount disposal are runtime/DOM behaviors not exercised by typecheck alone; needs a live browser check once 04-06 wires these into the page."

# Metrics
duration: 12min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 4: Portfolio Heatmap + P&L Chart Summary

**Recharts Treemap portfolio heatmap (sized by live weight, colored by P&L) and a lightweight-charts v5 line series of total portfolio value over time from /api/portfolio/history**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-04T23:47:00Z
- **Completed:** 2026-07-04T23:48:04Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `PortfolioHeatmap.tsx`: recharts `<Treemap>` with a custom SVG cell renderer — one rectangle per position, sized by `quantity × live price`, colored green/red by unrealized P&L sign with opacity scaled by `|pct_change|`, ticker + P&L labels when the cell is large enough, and an explicit empty state.
- `PnLChart.tsx`: lightweight-charts v5 line series plotting `total_value` over `recorded_at` from `Snapshot[]`, using the v5 `chart.addSeries(LineSeries, ...)` API, with resize handling, unmount disposal, and an empty-state overlay that keeps the chart container mounted so data arriving after first render still initializes correctly.

## Task Commits

Each task was committed atomically:

1. **Task 1: PortfolioHeatmap — recharts Treemap sized by weight, colored by P&L** - `8e2efc9` (feat)
2. **Task 2: PnLChart — lightweight-charts line of total value over time** - `1f7cb9b` (feat)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified
- `frontend/components/PortfolioHeatmap.tsx` - Treemap heatmap of positions sized by weight, colored by P&L
- `frontend/components/PnLChart.tsx` - Line chart of total portfolio value over time

## Decisions Made
- Heatmap weight/P&L recompute from the live `PriceMap` (SSE) when available, falling back to the position's last-known `current_price` — keeps the heatmap live without depending on a portfolio re-fetch cadence.
- `recorded_at` ISO timestamps are floored to whole seconds and monotonically nudged forward on collision (rather than deduped/dropped) so every snapshot still contributes a point and lightweight-charts' strictly-ascending-time invariant holds.
- Kept the chart's DOM container always mounted (overlay message for the empty state, not a conditional unmount) to avoid a stale-ref bug where history arriving after the initial empty render would never get a chart instance.

## Deviations from Plan

None - plan executed exactly as written. Context7/ctx7 were unavailable in this environment; verified the recharts v2 `Treemap` `content` prop contract and the lightweight-charts v5 `addSeries(LineSeries, ...)` signature directly against the installed packages' `.d.ts` files in `frontend/node_modules` instead.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both components are self-contained (`Position[]`/`PriceMap` and `Snapshot[]` props respectively) and ready for 04-06 to import and wire into the bottom-band layout alongside the positions table and trade bar.
- No blockers. Full-build verification (`npm run build`) is deferred to 04-06 per this plan's `<verification>` note, since other wave-2/3 components (page assembly, watchlist, chat) are still in flight from parallel executors.

---
*Phase: 04-frontend-terminal-ui*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: frontend/components/PortfolioHeatmap.tsx
- FOUND: frontend/components/PnLChart.tsx
- FOUND: commit 8e2efc9
- FOUND: commit 1f7cb9b
