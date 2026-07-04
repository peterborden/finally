# Requirements: FinAlly — AI Trading Workstation

**Defined:** 2026-07-04
**Core Value:** The user watches live prices stream and can trade — manually or via the AI — with portfolio, positions, and P&L updating instantly.

## v1 Requirements

Requirements for the initial release. Each maps to a roadmap phase. The market data subsystem (MKT-*) is already shipped and validated; it is listed for traceability but requires no new work.

### Market Data (Validated — existing)

- [x] **MKT-01**: Prices stream over SSE at `GET /api/stream/prices` with change direction
- [x] **MKT-02**: Simulator generates correlated GBM prices with random events (default source)
- [x] **MKT-03**: Massive/Polygon.io source used when `MASSIVE_API_KEY` is set
- [x] **MKT-04**: Thread-safe price cache shared by all consumers; tickers can be added/removed

### Platform Foundation

- [ ] **APP-01**: FastAPI app (`app/main.py`) starts the market data source and mounts the SSE router on startup
- [ ] **APP-02**: `GET /api/health` returns a health check for Docker/deployment
- [ ] **APP-03**: FastAPI serves the exported Next.js frontend as static files from `/`
- [ ] **DB-01**: SQLite database is lazily created and seeded on first request if absent (no migration step)
- [ ] **DB-02**: Schema includes `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`, each with a `user_id` column defaulting to `"default"`
- [ ] **DB-03**: Default seed creates a profile with $10,000 cash and a 10-ticker watchlist (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX)

### Watchlist

- [ ] **WATCH-01**: User can view the watchlist with each ticker's latest price (`GET /api/watchlist`)
- [ ] **WATCH-02**: User can add a ticker (`POST /api/watchlist`), which begins streaming in the market source
- [ ] **WATCH-03**: User can remove a ticker (`DELETE /api/watchlist/{ticker}`), which stops it streaming

### Portfolio & Trading

- [ ] **PORT-01**: User can view portfolio state — positions, cash balance, total value, unrealized P&L (`GET /api/portfolio`)
- [ ] **PORT-02**: User can execute a market order (`POST /api/portfolio/trade`) that fills instantly at the current price
- [ ] **PORT-03**: Buys are rejected with a clear error when cash is insufficient; sells rejected when shares are insufficient
- [ ] **PORT-04**: Positions and cash update correctly on buy/sell, including fractional shares and average-cost math
- [ ] **PORT-05**: User can view portfolio value over time (`GET /api/portfolio/history`)
- [ ] **PORT-06**: Portfolio value is snapshotted every 30 seconds and immediately after each trade

### AI Chat Assistant

- [ ] **CHAT-01**: User can send a chat message (`POST /api/chat`) and receive a complete structured response (message + executed actions)
- [ ] **CHAT-02**: The LLM call uses LiteLLM → OpenRouter (Cerebras, `openrouter/openai/gpt-oss-120b`) with structured output, via the `cerebras-inference` skill
- [ ] **CHAT-03**: The assistant loads portfolio context (cash, positions with P&L, watchlist with live prices, total value) and recent history into the prompt
- [ ] **CHAT-04**: Trades specified by the LLM auto-execute through the same validation as manual trades; failures are surfaced in the response
- [ ] **CHAT-05**: Watchlist changes specified by the LLM auto-apply
- [ ] **CHAT-06**: Conversation and executed actions are persisted in `chat_messages`
- [ ] **CHAT-07**: `LLM_MOCK=true` returns deterministic mock responses (no API call) for tests/CI

### Frontend Terminal UI

- [ ] **UI-01**: Dark, data-dense Bloomberg-style single-page layout with the specified color scheme (Tailwind custom theme)
- [ ] **UI-02**: Watchlist grid shows current price flashing green/red on change (fading ~500ms), daily change %, and a progressive sparkline accumulated from SSE
- [ ] **UI-03**: Clicking a watchlist ticker selects it in a larger main chart area (price over time)
- [ ] **UI-04**: Portfolio heatmap/treemap sizes positions by weight and colors by P&L
- [ ] **UI-05**: P&L line chart plots total portfolio value over time from `portfolio_snapshots`
- [ ] **UI-06**: Positions table shows ticker, quantity, avg cost, current price, unrealized P&L, % change
- [ ] **UI-07**: Trade bar (ticker, quantity, buy/sell) executes market orders instantly with no confirmation dialog
- [ ] **UI-08**: Collapsible AI chat panel with scrolling history, loading indicator, and inline trade/watchlist confirmations
- [ ] **UI-09**: Header shows live total value, cash balance, and a connection status dot (green/yellow/red)
- [ ] **UI-10**: Frontend consumes SSE via native `EventSource` with automatic reconnection

### Delivery & Packaging

- [ ] **PKG-01**: Multi-stage Dockerfile builds the Next.js static export (Node) and runs FastAPI serving both API and static assets on port 8000
- [ ] **PKG-02**: SQLite persists via a volume mount (`db/finally.db` ↔ `/app/db`)
- [ ] **PKG-03**: Idempotent start/stop scripts for macOS/Linux and Windows, plus `.env.example`
- [ ] **PKG-04**: Playwright E2E tests in `test/` (with `docker-compose.test.yml`) run under `LLM_MOCK=true` covering the key user scenarios

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Enhancements

- **V2-01**: Optional cloud deployment (Terraform for AWS App Runner / Render) in `deploy/`
- **V2-02**: Configurable Massive polling cadence per paid tier
- **V2-03**: Persisted price history (beyond current+previous) for server-side charting

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Authentication / multi-user | Single-user by design; `user_id` column reserved for future multi-user without migration |
| Limit orders / order book / partial fills / fees | Market orders only — keeps portfolio math simple |
| WebSockets | SSE covers one-way server→client push with universal support |
| Postgres / DB server | SQLite is self-contained and zero-config |
| Token-by-token LLM streaming | Cerebras inference is fast enough; loading indicator suffices |
| Trade confirmation dialogs | Deliberate — simulated money, fluid agentic demo |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MKT-01…04 | — (existing) | Complete |
| APP-01…03, DB-01…03 | Phase [N] | Pending |
| WATCH-01…03 | Phase [N] | Pending |
| PORT-01…06 | Phase [N] | Pending |
| CHAT-01…07 | Phase [N] | Pending |
| UI-01…10 | Phase [N] | Pending |
| PKG-01…04 | Phase [N] | Pending |

**Coverage:**
- v1 requirements (new): 33 total (excludes 4 already-validated MKT-*)
- Mapped to phases: filled by roadmapper
- Unmapped: filled by roadmapper

---
*Requirements defined: 2026-07-04*
*Last updated: 2026-07-04 after initialization*
