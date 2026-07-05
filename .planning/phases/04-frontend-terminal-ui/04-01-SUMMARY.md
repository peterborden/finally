---
phase: 04-frontend-terminal-ui
plan: 01
subsystem: ui
tags: [nextjs, typescript, tailwind, sse, eventsource, vitest]

# Dependency graph
requires:
  - phase: 01-platform-foundation
    provides: SQLite schema, seed data, env-driven backend config
  - phase: 02-portfolio-watchlist (or equivalent prior phase)
    provides: "/api/portfolio, /api/watchlist REST response shapes"
  - phase: 03-ai-chat (or equivalent prior phase)
    provides: "/api/chat request/response shape"
provides:
  - Buildable Next.js (app router) + TypeScript static-export project in frontend/ producing frontend/out
  - Locked dark Tailwind theme tokens (base, panel, border-muted, accent, blue, purple, up, down)
  - lib/types.ts mirroring all backend response/SSE shapes
  - lib/api.ts relative /api/* fetch client surfacing backend HTTPException detail on error
  - lib/useLivePrices.ts SSE hook (EventSource) with tested applyPriceEvent merge/history-cap logic and connection status
affects: [04-frontend-terminal-ui (waves 2+), 05-deployment]

# Tech tracking
tech-stack:
  added: [next@15, react@19, typescript@5, tailwindcss@3, postcss, autoprefixer, lightweight-charts@5, recharts@2, vitest@3]
  patterns:
    - "Static export (output:'export', images.unoptimized) — no server-side Next.js runtime, served by FastAPI StaticFiles"
    - "Pure-function extraction for hook logic (applyPriceEvent) to unit-test SSE merge/cap behavior without a DOM/EventSource"
    - "Relative-only /api/* fetch calls — same-origin, no CORS"

key-files:
  created:
    - frontend/package.json
    - frontend/next.config.mjs
    - frontend/tsconfig.json
    - frontend/postcss.config.mjs
    - frontend/tailwind.config.ts
    - frontend/.gitignore
    - frontend/next-env.d.ts
    - frontend/app/layout.tsx
    - frontend/app/globals.css
    - frontend/app/page.tsx
    - frontend/lib/types.ts
    - frontend/lib/api.ts
    - frontend/lib/useLivePrices.ts
    - frontend/lib/useLivePrices.test.ts
  modified:
    - .gitignore (root — scoped an over-broad `lib/` pattern to `/lib/` so it no longer shadows frontend/lib)

key-decisions:
  - "Pinned next@^15/react@^19/typescript@^5/tailwindcss@^3 (not v4) per the locked stack in 04-CONTEXT.md, hand-authoring config instead of create-next-app"
  - "Added vitest as the frontend unit test runner (not in original PLAN.md but required by this plan's TDD task) with a colocated *.test.ts convention"
  - "applyPriceEvent uses the SSE event's own `timestamp` field (not Date.now()) for history points, keeping the merge function pure and deterministic for testing"

patterns-established:
  - "SSE hook logic split into an exported pure helper + a thin React effect wrapper, so behavior is unit-testable without jsdom"
  - "API client throws Error(detail) from FastAPI's {detail} HTTPException body on any non-ok response"

requirements-completed: [UI-01, UI-10]

coverage:
  - id: D1
    description: "npm run build produces a static export at frontend/out with an index.html"
    requirement: "UI-01"
    verification:
      - kind: other
        ref: "npm --prefix frontend run build; test -f frontend/out/index.html"
        status: pass
    human_judgment: false
  - id: D2
    description: "Locked dark theme tokens (base #0d1117, panel #1a1a2e, border-muted #2a2a3a, accent #ecad0a, blue #209dd7, purple #753991, up #3fb950, down #f85149) available as Tailwind classes; price-flash CSS transitions defined"
    requirement: "UI-01"
    verification:
      - kind: other
        ref: "frontend/tailwind.config.ts theme.colors; frontend/app/globals.css .flash-up/.flash-down"
        status: pass
    human_judgment: true
    rationale: "Exact color rendering and animation feel are visual — a human should eyeball the built page once wave-2 components mount into it."
  - id: D3
    description: "useLivePrices opens EventSource('/api/stream/prices'), parses the ticker-keyed SSE payload, maintains per-ticker price history capped at N points, and exposes connection status (connecting/connected/reconnecting)"
    requirement: "UI-10"
    verification:
      - kind: unit
        ref: "frontend/lib/useLivePrices.test.ts#applyPriceEvent (5 tests: single-ticker merge, multi-ticker merge, history append, no-clobber, history cap)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 01: Frontend Scaffold Summary

**Hand-authored Next.js 15 (app router) + TypeScript static-export project in `frontend/` with the locked Bloomberg-dark Tailwind v3 theme, a typed `/api/*` client, and a unit-tested `useLivePrices` SSE hook that parses the backend's ticker-keyed price stream.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-04T23:37:05-04:00
- **Completed:** 2026-07-05T03:40:48Z
- **Tasks:** 3/3 completed
- **Files modified:** 15 (14 created in `frontend/`, 1 modified at repo root)

## Accomplishments
- Buildable Next.js static-export project (`npm run build` → `frontend/out/index.html`), the exact directory FastAPI's `FRONTEND_DIST` serves
- Tailwind v3 theme carrying all eight locked hex tokens plus a monospace/tabular-nums setup for price columns
- `globals.css` price-flash utilities (`.flash-up`/`.flash-down`, 500ms background-color transition) ready for wave-2 components to apply on price change
- `lib/types.ts` mirroring every backend response shape (`PriceEvent`, `WatchlistEntry`, `Position`, `Portfolio`, `TradeResponse`, `Snapshot`, `ChatAction`, `ChatResponse`), with an explicit doc comment distinguishing the `Position.pct_change` fraction from the `PriceEvent`/`WatchlistEntry` `change_percent` percentage
- `lib/api.ts` relative-only `/api/*` fetch wrappers that throw the backend's `detail` string on error
- `lib/useLivePrices.ts`: a `'use client'` hook wrapping `EventSource('/api/stream/prices')`, delegating the ticker-keyed merge + history-cap logic to an exported pure `applyPriceEvent` helper, covered by 5 vitest unit tests written before the implementation (RED → GREEN)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold the Next.js static-export project + install dependencies** - `14520bd` (feat)
2. **Task 2: Theme shell — layout, globals.css (flash animation), placeholder page** - `c2f3b90` (feat)
3. **Task 3: Shared types, /api client, and the useLivePrices SSE hook (TDD)** - `b3cb9d8` (feat)

**Plan metadata:** _pending — final docs commit created after this summary_

## Files Created/Modified
- `frontend/package.json` - scripts (dev/build/start/typecheck/lint/test) + pinned deps (next@15, react@19, tailwindcss@3, lightweight-charts@5, recharts@2, vitest@3)
- `frontend/next.config.mjs` - `output: 'export'`, `images.unoptimized: true`
- `frontend/tsconfig.json` - strict TS, `moduleResolution: bundler`, `@/*` path alias
- `frontend/postcss.config.mjs` - tailwindcss + autoprefixer plugins
- `frontend/tailwind.config.ts` - locked theme colors + mono font stack
- `frontend/.gitignore` - ignores node_modules/.next/out; commits next-env.d.ts
- `frontend/next-env.d.ts` - Next.js TS reference file (auto-updated by `next build` to reference `.next/types/routes.d.ts`)
- `frontend/app/layout.tsx` - root layout, dark theme body classes, imports globals.css
- `frontend/app/globals.css` - Tailwind directives, base background, `.flash-up`/`.flash-down`, `.tabular`
- `frontend/app/page.tsx` - placeholder terminal shell (stub for plan 04-06)
- `frontend/lib/types.ts` - all shared backend-mirroring types
- `frontend/lib/api.ts` - `getWatchlist`, `addTicker`, `removeTicker`, `getPortfolio`, `trade`, `getHistory`, `sendChat`
- `frontend/lib/useLivePrices.ts` - `applyPriceEvent` pure helper + `useLivePrices` hook
- `frontend/lib/useLivePrices.test.ts` - vitest coverage of `applyPriceEvent`
- `.gitignore` (root) - scoped `lib/`/`lib64/` to `/lib/`/`/lib64/` (see Deviations)

## Decisions Made
- Wrote all Next.js/Tailwind/TS config files by hand rather than running `create-next-app` interactively, per the plan's explicit instruction.
- Extracted `applyPriceEvent` as a standalone exported function so the SSE merge/cap logic is unit-testable in Node (vitest, no jsdom needed) rather than requiring a mocked `EventSource`.
- Used the SSE event's own `timestamp` (unix seconds, from the backend) as each history point's `t`, not `Date.now()`, keeping the merge pure/deterministic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Root `.gitignore` `lib/` pattern was shadowing `frontend/lib/`**
- **Found during:** Task 3, staging `frontend/lib/*.ts` for commit
- **Issue:** The repo root `.gitignore` carries the standard Python-boilerplate entries `lib/` and `lib64/` (intended for Python build/venv artifacts). Being unanchored, they matched `frontend/lib/` anywhere in the tree, silently hiding the new `types.ts`/`api.ts`/`useLivePrices.ts`/`useLivePrices.test.ts` from `git status` and `git add`.
- **Fix:** Anchored both patterns to the repo root (`/lib/`, `/lib64/`) so they still ignore an eventual top-level Python build dir but no longer match nested source directories like `frontend/lib/`.
- **Files modified:** `.gitignore` (root)
- **Verification:** `git check-ignore -v frontend/lib/types.ts` returns nothing (no longer ignored) after the fix; `git status` shows the four `frontend/lib/*.ts` files as trackable.
- **Committed in:** `b3cb9d8` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to commit the plan's own deliverable files; no scope creep. Fixing this also surfaced several pre-existing, unrelated `.claude/**/lib/` tool directories as untracked — these are out of scope for this plan and were left untouched (not staged, not modified).

## Issues Encountered
- The `frontend/lib/` gitignore collision above was the only issue; resolved inline as a Rule 3 auto-fix before the Task 3 commit.
- Minor process note: this plan's TDD task (Task 3) followed the RED→GREEN discipline (test written and confirmed failing via `npx vitest run` before `useLivePrices.ts` existed, then confirmed passing after implementation) but both files were committed together in a single `feat` commit rather than as separate `test(...)` then `feat(...)` commits, since the task frontmatter marks the whole task `tdd="true"` rather than the plan itself being `type: tdd`. No functional impact — RED/GREEN evidence is documented here.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `frontend/` now builds cleanly (`npm run build` → `frontend/out/index.html`), so Phase 5's Dockerfile can build and copy this output immediately.
- `lib/types.ts`, `lib/api.ts`, and `lib/useLivePrices.ts` are the shared foundation every wave-2 Phase 4 plan (Header, Watchlist, PriceChart, PnLChart, PortfolioHeatmap, PositionsTable, TradeBar, ChatPanel) will import from — no further scaffolding needed before those plans start.
- `app/page.tsx` is an intentional placeholder; plan 04-06 is expected to replace it with the full Bloomberg layout composing the wave-2 components.
- No blockers identified.

---
*Phase: 04-frontend-terminal-ui*
*Completed: 2026-07-04*

## Self-Check: PASSED

All 14 created files (frontend config, app shell, lib modules) and `frontend/out/index.html` verified present on disk. All 3 task commits (`14520bd`, `c2f3b90`, `b3cb9d8`) verified present in git history.
