---
phase: 04-frontend-terminal-ui
plan: 06
subsystem: ui
tags: [react, nextjs, sse, integration, static-export]

# Dependency graph
requires:
  - phase: 04-01
    provides: Next.js 15 TS app scaffold, tailwind theme, lib/types.ts, lib/api.ts, lib/useLivePrices.ts
  - phase: 04-02
    provides: Header, ConnectionDot, Watchlist, Sparkline components
  - phase: 04-03
    provides: PriceChart, PnLChart (lightweight-charts)
  - phase: 04-04
    provides: PositionsTable, PortfolioHeatmap, TradeBar
  - phase: 04-05
    provides: ChatPanel
provides:
  - "app/page.tsx: the assembled single-page Bloomberg-style terminal wiring all eight components to shared SSE/portfolio/watchlist state"
  - "Verified static export (frontend/out) served end-to-end by the existing FastAPI backend via FRONTEND_DIST"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single useLivePrices() subscription in the page root, threaded down as props (prices/history/status) rather than each component opening its own SSE connection"
    - "refreshWatchlist / refreshPortfolio / refreshAll callback trio: trade (TradeBar) and chat (ChatPanel) actions call refreshAll; watchlist add/remove calls refreshWatchlist only"

key-files:
  created: []
  modified: [frontend/app/page.tsx]

key-decisions:
  - "Bottom band laid out as a 3-column grid (heatmap / P&L chart / positions table) with a full-width TradeBar strip beneath it, rather than a single flex row, so PositionsTable can scroll independently when it grows"
  - "selectedTicker defaults to the first watchlist entry once the watchlist loads (effect keyed on watchlist+selectedTicker) but never overrides a user's own selection afterward"
  - "refreshWatchlist/refreshPortfolio swallow fetch errors and keep the last-known state rendered rather than clearing the UI on a transient network blip, matching the resilience posture used inside Watchlist/TradeBar/ChatPanel's own error handling"

patterns-established:
  - "Page-root-owns-shared-state: page.tsx is the only component that fetches /api/portfolio, /api/watchlist, /api/portfolio/history and holds selectedTicker; all eight components remain presentational/self-contained aside from their own local UI state"

requirements-completed: [UI-01]

coverage:
  - id: D1
    description: "Single dark, data-dense Bloomberg-style page assembling header, watchlist, main chart, portfolio heatmap, P&L chart, positions table, trade bar, and chat panel in the locked color scheme"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck (tsc --noEmit) -> exit 0"
        status: pass
      - kind: integration
        ref: "npm --prefix frontend run build -> frontend/out/index.html (9653 bytes) produced"
        status: pass
      - kind: e2e
        ref: "FRONTEND_DIST=frontend/out LLM_MOCK=true uvicorn app.main:app served on :8123; curl / returned 200 with full rendered layout (all 8 panels present in SSR HTML) and curl /api/health returned {\"status\":\"ok\"}"
        status: pass
    human_judgment: true
    rationale: "Live browser verification of visual polish (exact color scheme, price flash animations, sparkline fill-in, connection dot going green against the real market simulator, instant trade/chat interaction feel) requires a human or browser-driven UAT pass — delegated to the orchestrator per this plan's checkpoint:human-verify task. Automated checks (typecheck, build, static-export smoke test via curl) all pass and are captured above."
  - id: D2
    description: "Ticker selection drives the main chart; trades and chat actions refresh /api/portfolio and /api/watchlist so positions/cash/total update instantly"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "npm --prefix frontend run typecheck (tsc --noEmit) -> exit 0 (verifies onSelect/onTraded/onActions/onWatchlistChange prop wiring type-checks against each component's contract)"
        status: pass
    human_judgment: true
    rationale: "Confirming the refetch actually fires end-to-end (buy order -> portfolio panel updates; chat trade -> watchlist/portfolio update) requires exercising the running app with a live backend and browser — delegated to the orchestrator's live verification pass."

# Metrics
duration: 25min
completed: 2026-07-05
status: complete
---

# Phase 4 Plan 6: Terminal Assembly Summary

**Assembled `app/page.tsx` as the single-page Bloomberg terminal — header, watchlist, main chart, collapsible chat, and a heatmap/P&L/positions/trade-bar bottom band, all sharing one SSE subscription and refetch-on-action wiring — verified building to `frontend/out` and serving correctly through the existing FastAPI backend.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-05T03:30:00Z (approx.)
- **Completed:** 2026-07-05T03:56:00Z
- **Tasks:** 1 of 2 (Task 2 is a `checkpoint:human-verify` delegated to the orchestrator per execution instructions)
- **Files modified:** 1

## Accomplishments
- Rewrote `frontend/app/page.tsx` (replacing the 04-01 placeholder) as the full terminal root: mounts `useLivePrices()` once, fetches `/api/watchlist` + `/api/portfolio` + `/api/portfolio/history` on load, and holds `selectedTicker` state defaulting to the first watchlist ticker.
- Locked-layout assembly: `Header` top bar; left `Watchlist` (drives selection); center `PriceChart` for the selected ticker; right collapsible `ChatPanel`; bottom band with `PortfolioHeatmap` + `PnLChart` + a scrollable `PositionsTable`, plus a full-width `TradeBar` strip beneath.
- Wired `refreshWatchlist` / `refreshPortfolio` / `refreshAll` callbacks: `TradeBar.onTraded` and `ChatPanel.onActions` both call `refreshAll` (portfolio + history + watchlist); `Watchlist.onWatchlistChange` calls `refreshWatchlist` alone.
- `npm --prefix frontend run typecheck` and `npm --prefix frontend run build` both pass; `frontend/out/index.html` (9653 bytes) is produced.
- End-to-end smoke test: started the FastAPI backend with `FRONTEND_DIST=frontend/out LLM_MOCK=true` on a scratch port, confirmed `GET /` returns 200 with the fully assembled SSR HTML (all eight panels present — header, watchlist add-form, price chart placeholder, chat panel, heatmap/P&L/positions empty states, trade bar) and `GET /api/health` returns `{"status":"ok"}`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Assemble the terminal in page.tsx and wire shared state + refetch** - `4291c09` (feat)

**Task 2 (`checkpoint:human-verify`):** Not executed by this agent — automated verification (typecheck, build, static-export smoke test via curl against a live backend instance) was performed in its place per explicit orchestrator instruction that live visual/interactive verification is delegated to the orchestrator. See "Deferred to Orchestrator" below.

**Plan metadata:** committed alongside this SUMMARY as part of the final phase-completion commit.

## Files Created/Modified
- `frontend/app/page.tsx` - Full terminal assembly: shared SSE/portfolio/watchlist state, all eight components laid out per the locked Bloomberg-style design contract, refetch wiring for trades/chat/watchlist changes.

## Decisions Made
- Bottom band uses a 3-column CSS grid (heatmap / P&L chart / positions table) with an independent `overflow-y-auto` wrapper around `PositionsTable` so a long position list scrolls without pushing the trade bar off-screen, plus a full-width `TradeBar` strip below the grid.
- `selectedTicker` initialization is driven by an effect keyed on `[watchlist, selectedTicker]` that only sets a default when `selectedTicker === null`, so it never fights a user's manual selection after the watchlist has loaded.
- `refreshWatchlist`/`refreshPortfolio` catch and silently ignore fetch errors (keeping the last successfully fetched state on screen) rather than surfacing a page-level error state, consistent with how the underlying components already handle their own request failures inline.

## Deviations from Plan

None - plan executed exactly as written for Task 1. Task 2 (`checkpoint:human-verify`, gate="blocking") was intentionally not executed as a human-blocking checkpoint per the orchestrator's explicit instruction for this run: the orchestrator performs live visual verification separately, and this agent instead ran all available automated verification in its place (typecheck, build, and an end-to-end curl smoke test against a live backend instance serving `frontend/out`). This is a deliberate scope adjustment communicated by the invoking orchestrator, not an unplanned deviation under Rules 1-4.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. Live visual/interactive verification of the served terminal (browser rendering of the color scheme, price flash animations, progressive sparklines, connection dot, instant trade fill, and chat loading/action-chip flow) is deferred to the orchestrator, per its explicit instruction. Suggested verification steps (unchanged from the plan's Task 2 `how-to-verify`):

1. `npm --prefix frontend run build` (already verified passing; produces `frontend/out`).
2. `FRONTEND_DIST=$(pwd)/frontend/out LLM_MOCK=true uv run --project backend --extra dev uvicorn app.main:app --app-dir backend --port 8000` from the repo root.
3. `curl -s http://localhost:8000/ | grep -qi finally` and `curl -s http://localhost:8000/api/health` (both confirmed passing during this execution against a scratch port).
4. Open `http://localhost:8000` in a browser and visually confirm the dark Bloomberg-style scheme, live price flashes/sparklines, ticker-select-to-chart, positions/heatmap/P&L rendering, instant buy/sell fill, and the chat panel's loading indicator + inline action confirmations (LLM_MOCK mode).

## Next Phase Readiness
- Phase 4 (Frontend Terminal UI) is functionally complete: all ten UI requirements (UI-01..UI-10) are implemented across the six plans, and the static export builds and serves correctly through the existing FastAPI backend contract established in Phase 1.
- Ready for Phase 5 (deployment/Dockerfile wiring): the Dockerfile's Node build stage can run `npm --prefix frontend run build` and copy `frontend/out` into the image, then set `FRONTEND_DIST` accordingly — exactly the flow smoke-tested in this plan.
- Outstanding: the live, human-in-the-browser visual/interactive verification described in this plan's Task 2 has not been performed by a human yet — the orchestrator should complete that pass (or explicitly accept the automated evidence above) before considering Phase 4 fully closed out for UAT purposes.

---
*Phase: 04-frontend-terminal-ui*
*Completed: 2026-07-05*

## Self-Check: PASSED

- FOUND: frontend/app/page.tsx
- FOUND: frontend/out/index.html
- FOUND: 4291c09 (task 1 commit)
