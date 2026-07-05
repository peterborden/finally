# Roadmap: FinAlly — AI Trading Workstation

## Overview

FinAlly is a brownfield build: the market data subsystem (SSE streaming, GBM simulator, Massive client, thread-safe price cache, factory, tests — MKT-01..04) is already complete and validated under `backend/app/market/`. This roadmap layers the rest of the trading workstation on top of it, reading from the existing `PriceCache` (never the data sources directly). The journey moves from a bootable, self-seeding FastAPI app, to the watchlist/portfolio/trading REST APIs, to the AI chat assistant that can act on the portfolio, to the Bloomberg-style terminal UI that renders it all, and finally to one-command Docker packaging with end-to-end tests. Each phase delivers an observable capability that builds toward the core value: watch live prices stream and trade — manually or via the AI — with everything updating instantly.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Platform Foundation** - FastAPI app assembly, health check, static serving, and lazily-seeded SQLite database (completed 2026-07-05)
- [x] **Phase 2: Watchlist & Trading APIs** - REST endpoints for watchlist management and simulated portfolio trading (completed 2026-07-05)
- [x] **Phase 3: AI Chat Assistant** - LLM chat via Cerebras that analyzes the portfolio and auto-executes trades/watchlist changes (completed 2026-07-05)
- [ ] **Phase 4: Frontend Terminal UI** - Dark Bloomberg-style Next.js terminal streaming prices and driving all interactions
- [ ] **Phase 5: Packaging & E2E Delivery** - Single-command Docker container, persistent data, start/stop scripts, and Playwright E2E tests

## Phase Details

### Phase 1: Platform Foundation

**Goal**: A bootable FastAPI application that starts the existing market data subsystem, answers a health check, serves the static frontend directory, and lazily creates and seeds the SQLite database on first request.
**Mode:** mvp
**Depends on**: Nothing (first phase; builds on the existing MKT-01..04 market subsystem)
**Requirements**: APP-01, APP-02, APP-03, DB-01, DB-02, DB-03
**Success Criteria** (what must be TRUE):

  1. Starting the server brings the app up with the existing market data source running and the SSE stream live at `GET /api/stream/prices`
  2. `GET /api/health` returns a healthy status suitable for Docker/deployment checks
  3. On first request, a SQLite database is created at `db/finally.db` with all six tables (`users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`), seeded with a $10,000 profile and the 10 default tickers
  4. Navigating to `/` serves files from the static frontend directory (placeholder until the UI ships in Phase 4)

**Plans**: 2/2 plans complete

- [x] 01-01-PLAN.md — SQLite database layer: six-table schema, env-driven connection, seed data, idempotent lazy init (DB-01, DB-02, DB-03)
- [x] 01-02-PLAN.md — FastAPI app assembly: lifespan wiring market source + SSE, health check, static serving, lazy DB middleware (APP-01, APP-02, APP-03, DB-01)

### Phase 2: Watchlist & Trading APIs

**Goal**: Users can manage their watchlist and trade a simulated portfolio through REST endpoints backed by live prices from the shared price cache.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: WATCH-01, WATCH-02, WATCH-03, PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, PORT-06
**Success Criteria** (what must be TRUE):

  1. `GET /api/watchlist` returns the watched tickers with their latest live prices; `POST /api/watchlist` starts a ticker streaming and `DELETE /api/watchlist/{ticker}` stops it in the market source
  2. `POST /api/portfolio/trade` fills a market order instantly at the current price, updating cash and positions correctly (including fractional shares and average-cost math)
  3. Buys with insufficient cash and sells with insufficient shares are rejected with a clear error and leave the portfolio unchanged
  4. `GET /api/portfolio` returns positions, cash balance, total value, and unrealized P&L; `GET /api/portfolio/history` returns portfolio value snapshots over time
  5. Portfolio value is snapshotted every 30 seconds and immediately after each trade

**Plans**: 4/4 plans complete

- [x] 02-01-PLAN.md — Watchlist API: GET/POST/DELETE /api/watchlist wired to the market source (WATCH-01, WATCH-02, WATCH-03)
- [x] 02-02-PLAN.md — Pure trade engine: buy/sell average-cost math, fractional shares, insufficient-cash/shares rejection (PORT-03, PORT-04)
- [x] 02-03-PLAN.md — Portfolio + trading endpoints: GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history, immediate snapshot (PORT-01, PORT-02, PORT-03, PORT-05, PORT-06)
- [x] 02-04-PLAN.md — Periodic 30s portfolio snapshot background task in the lifespan (PORT-06)

### Phase 3: AI Chat Assistant

**Goal**: Users can chat with FinAlly, which loads live portfolio context, responds with structured output via Cerebras, and auto-executes trades and watchlist changes on their behalf.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07
**Success Criteria** (what must be TRUE):

  1. `POST /api/chat` returns a complete structured response (conversational message + executed actions) generated via LiteLLM → OpenRouter (Cerebras, `openrouter/openai/gpt-oss-120b`) using structured output through the `cerebras-inference` skill
  2. The assistant's prompt includes current portfolio context (cash, positions with P&L, watchlist with live prices, total value) and recent conversation history
  3. Trades and watchlist changes specified by the LLM auto-execute through the same validation as manual actions, with any failures surfaced back into the response
  4. The conversation and executed actions are persisted in `chat_messages` (actions stored as JSON)
  5. With `LLM_MOCK=true`, chat returns deterministic responses without calling OpenRouter

**Plans**: 3/3 plans complete

- [x] 03-01-PLAN.md — litellm dependency provisioning + supply-chain legitimacy checkpoint (CHAT-02)
- [x] 03-02-PLAN.md — LLM wrapper app/llm.py: structured schema, prompt builder, Cerebras call, deterministic mock (CHAT-02, CHAT-03, CHAT-07)
- [x] 03-03-PLAN.md — POST /api/chat: context load, auto-execute trades/watchlist via shared validated paths, persistence, tests (CHAT-01, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07)

### Phase 4: Frontend Terminal UI

**Goal**: Users see a dark, data-dense Bloomberg-style terminal that streams live prices and drives all trading, portfolio visualization, and AI chat interactions from one page.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10
**Success Criteria** (what must be TRUE):

  1. A dark, data-dense single-page layout renders with the specified color scheme (accent `#ecad0a`, blue `#209dd7`, purple `#753991`) and a header showing live total value, cash balance, and a connection-status dot (green/yellow/red)
  2. The watchlist grid consumes SSE via native `EventSource` with automatic reconnect, flashing prices green/red (fading ~500ms) with progressive sparklines and daily change %; clicking a ticker loads it in the main chart area
  3. The portfolio heatmap/treemap (sized by weight, colored by P&L), the P&L line chart over time, and the positions table all reflect current holdings
  4. The trade bar executes instant market orders (ticker, quantity, buy/sell) with no confirmation dialog
  5. The collapsible AI chat panel shows scrolling history, a loading indicator, and inline trade/watchlist confirmations

**Plans**: 1/6 plans executed

- [x] 04-01-PLAN.md — Scaffold Next.js TS static-export project: deps, dark Tailwind theme, types, /api client, useLivePrices SSE hook (UI-01, UI-10)
- [ ] 04-02-PLAN.md — Watchlist grid (flash, change %, progressive SVG sparkline, add/remove/select) + main PriceChart (lightweight-charts) (UI-02, UI-03)
- [ ] 04-03-PLAN.md — Header (live total/cash + connection dot), PositionsTable, TradeBar (instant market orders, no confirm) (UI-06, UI-07, UI-09)
- [ ] 04-04-PLAN.md — PortfolioHeatmap (recharts Treemap sized-by-weight colored-by-P&L) + PnLChart (lightweight-charts from /api/portfolio/history) (UI-04, UI-05)
- [ ] 04-05-PLAN.md — Collapsible AI ChatPanel: history, loading indicator, inline action confirmations, refetch on actions (UI-08)
- [ ] 04-06-PLAN.md — Assemble the single-page Bloomberg terminal in app/page.tsx; wire selection + refetch; build frontend/out; human-verify served app (UI-01)

**UI hint**: yes

### Phase 5: Packaging & E2E Delivery

**Goal**: The entire application runs from a single Docker command with persistent data, cross-platform launch scripts, and passing end-to-end tests.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04
**Success Criteria** (what must be TRUE):

  1. A multi-stage Dockerfile builds the Next.js static export (Node) and runs FastAPI serving both the API and the static assets on port 8000
  2. The SQLite database persists across container restarts via the volume mount (`db/finally.db` ↔ `/app/db`)
  3. Idempotent start/stop scripts for macOS/Linux and Windows, plus `.env.example`, let a user launch the app with one command
  4. Playwright E2E tests in `test/` (with `docker-compose.test.yml`) run under `LLM_MOCK=true` and cover the key user scenarios (fresh start, add/remove ticker, buy/sell, AI chat)

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Platform Foundation | 2/2 | Complete   | 2026-07-05 |
| 2. Watchlist & Trading APIs | 4/4 | Complete   | 2026-07-05 |
| 3. AI Chat Assistant | 3/3 | Complete   | 2026-07-05 |
| 4. Frontend Terminal UI | 1/6 | In Progress|  |
| 5. Packaging & E2E Delivery | 0/TBD | Not started | - |
