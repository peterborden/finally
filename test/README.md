# FinAlly — E2E & API Contract Test Suite

Playwright suite covering every key scenario in `planning/PLAN.md` §12, asserting the
exact API shapes in `planning/BUILD_CONTRACT.md` §5 and the UI in PLAN §10.

## Layout

```
test/
├── api/                     # HTTP contract tests (no browser) — §5 shapes
│   ├── 01-health-and-fresh.spec.ts   §5.8 health, §5.1 portfolio, §5.4 watchlist seed
│   ├── 02-watchlist.spec.ts          §5.5 add (201), §5.6 delete (200/404), normalization
│   ├── 03-trade.spec.ts              §5.2 buy/sell + validation-failure (insufficient cash/shares)
│   ├── 04-history.spec.ts            §5.3 snapshots, grows on trade, chronological
│   ├── 05-chat.spec.ts               §5.7 chat (LLM_MOCK) auto-executes "buy N TICKER"
│   └── 06-sse.spec.ts                §5.9 SSE stream shape + live updates
├── e2e/                     # Browser UI tests — PLAN §10 / §12
│   ├── 01-fresh-start.spec.ts        10-ticker watchlist, $10k, streaming, connected dot
│   ├── 02-watchlist.spec.ts          add / remove ticker via UI
│   ├── 03-trade.spec.ts              buy (cash↓, position appears) / sell (cash↑, position gone)
│   ├── 04-portfolio-viz.spec.ts      heatmap tiles colored, positions table, P&L chart has points
│   ├── 05-chat.spec.ts               chat message → reply → inline trade execution
│   └── 06-sse-resilience.spec.ts     disconnect → reconnect → prices resume
├── support/                 # selectors (DOM contract), api/ui/sse helpers
├── playwright.config.ts     # two projects: `api` (request-only) and `e2e` (Chromium)
├── docker-compose.test.yml  # app container + Playwright container (LLM_MOCK=true)
├── RUN.md                   # exact orchestrator run steps
└── package.json
```

Two Playwright **projects**:
- **`api`** — pure HTTP, needs only backend + db + llm. Runs first; `e2e` depends on it.
- **`e2e`** — Chromium, drives the frontend UI. Needs the full assembled app.

## Quick start (local, app already running on :8000)

```bash
cd test
npm install
npx playwright install --with-deps chromium
BASE_URL=http://localhost:8000 npx playwright test            # everything
BASE_URL=http://localhost:8000 npx playwright test --project=api   # contract only
```

The app must be running with `LLM_MOCK=true` (deterministic chat) and no
`MASSIVE_API_KEY` (built-in simulator). See `RUN.md`.

## Containerized (recommended — matches CI)

```bash
# from repo root
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

The `playwright` service exit code is the suite result. Report is written to
`test/playwright-report/`.

## Selector / DOM contract

E2E specs prefer `data-testid` values defined in `support/selectors.ts` and fall back
to role/text where possible. The Frontend engineer is asked (via `planning/BUILD_LOG.md`)
to add those testids so the UI assertions are exact and stable.

## Notes on state

Trades mutate the single shared (single-user) DB, so specs run **serially**
(`workers: 1`, `fullyParallel: false`). Each mutating spec cleans up after itself.
For a pristine `$10,000 / no positions` assertion, run against a **fresh DB volume**
(the compose file uses an ephemeral named volume, so each `up` after `down -v` is clean).
