---
phase: 04-frontend-terminal-ui
plan: 02
subsystem: ui
tags: [react, nextjs, lightweight-charts, svg, typescript]

# Dependency graph
requires:
  - phase: 04-frontend-terminal-ui (04-01)
    provides: Next.js TS app scaffold, Tailwind theme tokens, lib/types.ts, lib/api.ts, lib/useLivePrices.ts (SSE hook + applyPriceEvent)
provides:
  - Sparkline.tsx — hand-rolled SVG polyline, progressive fill (empty state under 2 points), up/down/flat color from first-vs-last price
  - Watchlist.tsx — live watchlist grid: price/change% from useLivePrices, .flash-up/.flash-down cell flash on price change, row selection, add/remove wired to lib/api
  - PriceChart.tsx — lightweight-charts v5 line series of the selected ticker's accumulated SSE ticks
affects: [04-06 (page assembly wires Watchlist + PriceChart into the left column / center chart area)]

# Tech tracking
tech-stack:
  added: []  # lightweight-charts already in package.json from 04-01 scaffold
  patterns:
    - "lightweight-charts v5 series creation via chart.addSeries(LineSeries, options) (v4 addLineSeries removed)"
    - "Chart component keeps its DOM container ref always mounted; empty-state message renders as an absolutely-positioned overlay so ticker/points changes never require a second ref-wiring effect"
    - "Price flash: ref-tracked previous price per key + setTimeout-managed class state, matching app/globals.css .flash-up/.flash-down 500ms transition"

key-files:
  created:
    - frontend/components/Sparkline.tsx
    - frontend/components/Watchlist.tsx
    - frontend/components/PriceChart.tsx
  modified: []

key-decisions:
  - "Sparkline is pure/presentational (points, width, height, color) with no dependency on useLivePrices — Watchlist passes history[ticker] in, keeping the SVG component trivially testable in isolation"
  - "PriceChart mounts the chart once (empty-deps effect) and only ever calls series.setData()/clears it on ticker or points change, rather than recreating/destroying the chart on ticker switch — avoids a stale-ref bug where selecting a ticker before the container has ever rendered would permanently skip chart creation"
  - "PriceChart drops any history point whose timestamp doesn't strictly increase from the last accepted one before calling series.setData(), since lightweight-charts throws on non-ascending time values and backend timestamps are float time.time() values without a uniqueness guarantee"

patterns-established:
  - "Empty-state overlay pattern for imperative-DOM chart components (lightweight-charts): never conditionally unmount the ref container, only overlay a message on top of it"

requirements-completed: [UI-02, UI-03]

coverage:
  - id: D1
    description: "Watchlist grid shows each ticker's live price flashing green/red on change (fading ~500ms), daily change %, and a progressive SVG sparkline"
    requirement: "UI-02"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Flash timing/fade, color correctness, and progressive sparkline fill-in are runtime/visual behaviors not exercised by typecheck alone; needs a live browser check once 04-06 wires this into the page."
  - id: D2
    description: "Add-ticker input and per-row × control call the backend and update the list; row click selects a ticker"
    requirement: "UI-02"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Add/remove/select are interaction flows against the live backend; needs a manual click-through once wired into the full page in 04-06."
  - id: D3
    description: "PriceChart renders the selected ticker's accumulated ticks as a lightweight-charts v5 line, updates on new ticks, and disposes cleanly on unmount"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck"
        status: pass
    human_judgment: true
    rationale: "Chart rendering, resize behavior, and unmount disposal are runtime/DOM behaviors not exercised by typecheck alone; needs a live browser check once 04-06 wires this into the page."

# Metrics
duration: 18min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 2: Watchlist Grid + Sparkline + PriceChart Summary

**Live watchlist grid (price flash, change%, hand-rolled SVG sparkline, add/remove/select) and a lightweight-charts v5 PriceChart for the selected ticker, both driven by the 04-01 useLivePrices SSE hook**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-04T23:30:00Z
- **Completed:** 2026-07-04T23:48:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `Sparkline.tsx`: dependency-free inline SVG polyline scaling a `{t, price}[]` window to a box, colored by first-vs-last price direction, with an explicit empty placeholder under 2 points so sparklines visibly fill in progressively.
- `Watchlist.tsx`: renders each watchlist entry's live price/change% from `useLivePrices`, flashes the price cell `.flash-up`/`.flash-down` for 500ms on every price change (ref-tracked previous price + timer cleanup), highlights the selected row, embeds a `Sparkline` per row, and wires an add-ticker form plus per-row remove button to `lib/api`, surfacing thrown `Error` details inline.
- `PriceChart.tsx`: mounts a `lightweight-charts` v5 chart via `chart.addSeries(LineSeries, ...)` once on mount, feeds it the selected ticker's accumulated history (filtering non-increasing timestamps), resizes via `ResizeObserver`, disposes on unmount, and shows an empty-state hint overlay when no ticker is selected or no ticks have arrived yet.

## Task Commits

Each task was committed atomically:

1. **Task 1: Sparkline (hand-rolled SVG) + Watchlist grid with flash, change %, add/remove, select** - `65d4199` (feat)
2. **Task 2: PriceChart — lightweight-charts line for the selected ticker** - `32ddd13` (feat)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified
- `frontend/components/Sparkline.tsx` - Presentational SVG sparkline, empty-state under 2 points
- `frontend/components/Watchlist.tsx` - Live watchlist grid with flash/change%/sparkline/select/add/remove
- `frontend/components/PriceChart.tsx` - lightweight-charts v5 line for the selected ticker

## Decisions Made
- Sparkline stays a pure presentational component (no hook dependency) so `Watchlist` fully controls what history slice it's given.
- PriceChart's chart-creation effect runs once on mount (empty deps) with the container div always rendered; the empty/"select a ticker" state is an absolutely-positioned overlay rather than a conditional unmount, avoiding a stale-ref bug where the chart would never be created if the component first mounted with `ticker === null`.
- Non-ascending history timestamps are defensively dropped before calling `series.setData()` since lightweight-charts requires strictly ascending time values and backend `timestamp` is a raw `time.time()` float with no uniqueness guarantee.

## Deviations from Plan

None - plan executed exactly as written. Context7/ctx7 were unavailable in this environment; confirmed the lightweight-charts v5 `chart.addSeries(LineSeries, ...)` signature (installed version 5.2.0) directly against `frontend/node_modules/lightweight-charts/dist/typings.d.ts` instead.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `Watchlist` (`entries`, `prices`, `history`, `selected`, `onSelect`, `onWatchlistChange` props) and `PriceChart` (`ticker`, `points` props) are self-contained and ready for 04-06 to import into the left column / center chart area alongside the header, chat panel, and bottom-band components from the other wave-2 plans.
- No blockers. `npm --prefix frontend run typecheck` and `npm --prefix frontend run build` both pass with only these 3 files added (page.tsx untouched, per this plan's file scope).

---
*Phase: 04-frontend-terminal-ui*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: frontend/components/Sparkline.tsx
- FOUND: frontend/components/Watchlist.tsx
- FOUND: frontend/components/PriceChart.tsx
- FOUND: commit 65d4199
- FOUND: commit 32ddd13
