# Codebase Concerns

**Analysis Date:** 2026-07-04

## Critical Gaps — Major Components Not Yet Implemented

### Frontend Missing Entirely

**Issue:** The `frontend/` directory is empty. According to PLAN.md, this should be a complete Next.js TypeScript project.
**Files:** `frontend/` (no files)
**Impact:** Application cannot run — no UI exists to display market data, portfolio, or chat interface.
**Fix approach:** Create Next.js project structure with pages, components (watchlist, charts, trade bar, chat panel), and integration tests. Required components per PLAN.md:
  - Watchlist grid with price flash animations
  - Main chart area (ticker-selected chart)
  - Portfolio heatmap (treemap by position weight and P&L)
  - P&L history chart
  - Positions table
  - Trade execution bar (ticker, quantity, buy/sell)
  - AI chat panel with conversation history
  - Header with portfolio value and connection status
  - EventSource connection to `/api/stream/prices` for live price updates

### Main FastAPI Application Not Implemented

**Issue:** Backend has only the market data module. No main FastAPI app, no API route handlers.
**Files:** `backend/app/__init__.py` (empty except for doc string), no `main.py` or `app.py`
**Impact:** Cannot serve frontend, cannot expose any API endpoints listed in PLAN.md sections 8-9.
**Fix approach:** Create FastAPI application that:
  - Mounts the SSE streaming router from `app.market.stream`
  - Initializes database and price cache on startup
  - Implements all endpoints: `/api/portfolio/*`, `/api/watchlist/*`, `/api/chat`, `/api/health`
  - Serves static frontend files from the Next.js build output
  - Handles graceful shutdown of market data source

### Database Layer Completely Missing

**Issue:** No SQLite integration, no database models, no schema definitions, no initialization code.
**Files:** None in `backend/app/` for database
**Impact:** Cannot persist user portfolio, trades, positions, watchlist, or chat history. Application must restart to reset state.
**Fix approach:** Add database module with:
  - Schema definitions (SQL files) for: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`
  - SQLAlchemy or plain sqlite3 models and table initialization
  - Lazy initialization logic: on first request, create tables if missing, seed default user and watchlist
  - Connection pooling and thread safety
  - Files needed: `backend/app/db/schema.sql`, `backend/app/db/models.py`, `backend/app/db/__init__.py`

### API Endpoints Not Implemented

**Issue:** No portfolio management, watchlist management, or chat endpoints.
**Files:** None
**Impact:** Frontend cannot fetch/modify portfolio, manage watchlist, or chat with LLM.
**Fix approach:** Implement routers in `backend/app/`:
  - `portfolio.py` — GET `/api/portfolio`, POST `/api/portfolio/trade`, GET `/api/portfolio/history`
  - `watchlist.py` — GET `/api/watchlist`, POST `/api/watchlist`, DELETE `/api/watchlist/{ticker}`
  - `chat.py` — POST `/api/chat` with LLM integration and auto-trade execution
  - `health.py` — GET `/api/health` for health checks

### LLM Integration Completely Missing

**Issue:** No LiteLLM, no OpenRouter integration, no structured output parsing for chat.
**Files:** None
**Impact:** Chat panel cannot function. No AI-powered trade suggestions or analysis.
**Fix approach:** Add `backend/app/llm/` module with:
  - LLM client using LiteLLM → OpenRouter → Cerebras inference
  - Structured output schema parsing (Pydantic models for `message`, `trades`, `watchlist_changes`)
  - Prompt construction from portfolio context and conversation history
  - Trade validation and auto-execution logic
  - Error handling for malformed responses
  - Files needed: `backend/app/llm/client.py`, `backend/app/llm/schemas.py`, `backend/app/llm/__init__.py`
  - Dependencies to add: `litellm`, `pydantic`

### Environment Configuration Missing

**Issue:** No `.env.example` file, no documentation of required env vars.
**Files:** No `.env.example`
**Impact:** Developers cannot know what environment variables are required. Docker setup will fail without guidance.
**Fix approach:** Create `.env.example` listing:
  - `OPENROUTER_API_KEY` (required for chat)
  - `MASSIVE_API_KEY` (optional, defaults to simulator)
  - `LLM_MOCK=false` (optional, for testing)

### Docker Setup Incomplete

**Issue:** No Dockerfile, docker-compose.yml, or start/stop scripts.
**Files:** None
**Impact:** Cannot package or deploy application. Users cannot run with single command as specified in PLAN.md.
**Fix approach:** Create:
  - `Dockerfile` (multi-stage: Node → Python)
  - `docker-compose.yml` (optional convenience wrapper)
  - `scripts/start_mac.sh`, `scripts/stop_mac.sh` (macOS/Linux)
  - `scripts/start_windows.ps1`, `scripts/stop_windows.ps1` (Windows)

### E2E Test Infrastructure Missing

**Issue:** No E2E tests, no Playwright setup, no test docker-compose.
**Files:** No `test/` directory or `test/docker-compose.test.yml`
**Impact:** Cannot validate complete user flows. No automated testing of fresh-start scenario.
**Fix approach:** Set up:
  - `test/docker-compose.test.yml` (app + Playwright containers)
  - `test/e2e.spec.ts` (Playwright tests)
  - Key scenarios: fresh start, add/remove ticker, buy/sell, chat with mocked LLM

---

## Package Dependencies Missing or Incomplete

### Missing Database Driver

**Issue:** `pyproject.toml` has no SQLite or database client.
**Files:** `backend/pyproject.toml` line 1-21
**Impact:** Cannot store or retrieve any user data.
**Fix approach:** Add to `pyproject.toml` dependencies:
  - `sqlalchemy>=2.0.0` (or use plain sqlite3 with manual queries)
  - `pydantic>=2.0.0` (for data validation and structured outputs)

### Missing LLM Integration Library

**Issue:** No `litellm` in dependencies.
**Files:** `backend/pyproject.toml`
**Impact:** Cannot make LLM calls.
**Fix approach:** Add `litellm>=1.0.0` to dependencies.

### Missing Validation Library

**Issue:** No `pydantic` for request/response validation and structured outputs.
**Files:** `backend/pyproject.toml`
**Impact:** API endpoints will lack type safety and validation. Chat structured outputs cannot be parsed reliably.
**Fix approach:** Add `pydantic>=2.0.0` to dependencies.

---

## Potential Issues in Implemented Code

### Thread Safety in Simulator State Management

**Issue:** `GBMSimulator` in `backend/app/market/simulator.py` uses mutable state (`_prices`, `_params`, `_tickers`) without synchronization.
**Files:** `backend/app/market/simulator.py` lines 60-62, 79-117
**Impact:** If `step()` is called concurrently while `add_ticker()` or `remove_ticker()` modifies state, race condition could occur. Cholesky rebuild (line 172) is not atomic with reads.
**Risk level:** LOW (in practice, `SimulatorDataSource._run_loop()` is single-threaded event loop task, so concurrent calls are prevented by asyncio)
**Fix approach:** If scaling to multi-threaded scenarios, add locks around mutable state or use `asyncio.Lock` for Cholesky rebuilds.

### Floating-Point Precision in GBM Simulator

**Issue:** GBM math (line 98-101 in `simulator.py`) uses very small `dt` (~8.48e-8) with `exp()` and repeated multiplication. Over many steps, numerical precision could degrade.
**Files:** `backend/app/market/simulator.py` lines 98-101
**Impact:** Very long-running simulator (days/weeks) could accumulate rounding errors or drift from realistic prices.
**Risk level:** LOW (demo application, user sessions typically short)
**Fix approach:** Monitor long-running simulator for drift. Consider periodically re-normalizing prices or using higher-precision arithmetic for critical calculations.

### Massive API Error Handling Could Be Stricter

**Issue:** `MassiveDataSource._poll_once()` catches all `Exception` and logs (line 118-121 in `massive_client.py`).
**Files:** `backend/app/market/massive_client.py` lines 94-121
**Impact:** Silent failure on 401 (bad API key) or other terminal errors — user never notified that live data is unavailable. Polling continues to fail silently.
**Risk level:** MEDIUM (user thinks real data is flowing, but simulator fallback doesn't trigger)
**Fix approach:** Distinguish recoverable errors (429 rate limit, network timeouts) from terminal errors (401 auth, invalid tickers). Log terminal errors at WARN level with actionable messages. Consider a "real data unavailable" flag exposed to frontend.

### SSE Stream Does Not Handle Large Tick Count Well

**Issue:** `app/market/stream.py` line 81 serializes ALL tickers in each SSE event, every 500ms. With 100+ tickers, payload size grows linearly.
**Files:** `backend/app/market/stream.py` lines 78-83
**Impact:** Bandwidth waste. On slow connections, SSE events pile up and client lags.
**Risk level:** LOW (default 10 tickers, manageable)
**Fix approach:** If watchlist grows large, switch to delta-only events (send only changed tickers) or use a binary format (MessagePack) for compression.

### Cache Version Counter Not Reset on Restart

**Issue:** `PriceCache._version` is initialized to 0 and monotonically increments. If application restarts, version counter resets but client may be comparing to old version number.
**Files:** `backend/app/market/cache.py` line 21, 41
**Impact:** If frontend reconnects after app restart with an old version number in memory, it might skip the first price update thinking data is unchanged (unlikely edge case).
**Risk level:** VERY LOW (mitigated by EventSource automatic reconnection; version comparison is for optimization only)
**Fix approach:** No fix needed in practice. If it becomes an issue, prepend a server restart identifier to version numbers.

---

## Scaling and Architecture Concerns

### Single Lock on Price Cache Could Bottleneck

**Issue:** `PriceCache` uses a single `Lock()` (line 20 in `cache.py`) protecting all reads and writes.
**Files:** `backend/app/market/cache.py` lines 20, 29, 46, 49, 54, 59, 70, 74
**Impact:** If the application scales to many concurrent SSE clients or frequent trade execution, lock contention could cause latency spikes.
**Risk level:** LOW (single app instance, limited concurrency)
**Fix approach:** For future multi-client/multi-region deployment, consider a sharded cache or use `asyncio.Lock` instead of `threading.Lock`.

### No Connection Pooling for Database

**Issue:** When database layer is added, it will likely use direct SQLite connections without pooling.
**Files:** To be added
**Impact:** SQLite has limited concurrent write capability. Multiple trades could queue up.
**Risk level:** MEDIUM (SQLite is single-writer, but app is single-user)
**Fix approach:** Use SQLAlchemy with connection pooling. Keep write transactions short. For multi-user future, consider PostgreSQL.

### No Caching of Watchlist or Portfolio

**Issue:** Every request to `/api/portfolio` or `/api/watchlist` will likely query the database.
**Files:** To be added
**Impact:** Unnecessary I/O. With polling frontend, this could be chatty.
**Risk level:** LOW (database is local SQLite, latency acceptable)
**Fix approach:** Cache watchlist in memory, invalidate on modifications. Cache portfolio value for a few seconds.

---

## Security Considerations

### No Authentication or User Isolation

**Issue:** PLAN.md hardcodes `user_id = "default"` for single-user demo. No authentication layer.
**Files:** All database/API files to be added
**Impact:** Not a concern for demo, but schema is designed for multi-user and auth is not plugged in. Future deployment must add auth before exposing.
**Fix approach:** For production, integrate OAuth2 or JWTs before opening to internet. Currently acceptable for local demo.

### LLM API Key Exposed in Environment

**Issue:** `OPENROUTER_API_KEY` will be in `.env` file.
**Files:** `.env` (gitignored but present on disk)
**Impact:** API key on disk is a secret sprawl risk. If Docker volume is compromised, key is readable.
**Risk level:** LOW (local demo, controlled environment)
**Fix approach:** For cloud deployment, use secret manager (AWS Secrets, GCP Secret Manager). Document that `.env` must not be committed.

### No Rate Limiting on Chat Endpoint

**Issue:** `/api/chat` will not have rate limiting.
**Files:** To be added
**Impact:** User could spam chat and exhaust OpenRouter quota.
**Risk level:** MEDIUM (malicious user could drain API credits)
**Fix approach:** Add token-bucket rate limiting to `/api/chat`. Limit to 10 requests/minute per user.

### Massive API Key Passed in Plain HTTP

**Issue:** If deployed over HTTP (not HTTPS), `MASSIVE_API_KEY` could be logged or cached by proxies.
**Files:** `backend/app/market/factory.py` line 24
**Impact:** Risk of key exposure in logs or proxies.
**Risk level:** LOW (demo runs on localhost)
**Fix approach:** Document deployment as HTTPS-only. Never log API keys.

---

## Test Coverage Gaps

### Backend Market Data Well-Tested, Rest of App Has No Tests

**Issue:** 73 tests exist for market data (`backend/tests/market/`), but no tests for:
  - API route handlers (to be added)
  - Database models and initialization (to be added)
  - LLM integration and structured output parsing (to be added)
  - Portfolio math (P&L calculation, trade execution) — **not yet implemented**
  - Chat message history and action persistence — **not yet implemented**

**Files:** `backend/tests/market/` (comprehensive); no `backend/tests/api/`, `backend/tests/db/`, `backend/tests/llm/`
**Impact:** New code will lack confidence. Edge cases (negative balances, fractional shares, trade failures) not validated.
**Risk level:** MEDIUM (backend API endpoints are critical path)
**Fix approach:** As each module is implemented, add corresponding tests:
  - Trade execution: sufficient cash, insufficient shares, fractional shares, P&L calculation
  - Chat: structured output parsing, malformed responses, trade validation failures
  - Database: schema initialization, migrations, seed data
  - API: status codes, response shapes, error cases

### No Frontend Unit or Integration Tests

**Issue:** Frontend will be built but not tested.
**Files:** Frontend not yet created
**Impact:** UI bugs (price flash not triggering, chat not updating) only caught manually.
**Risk level:** MEDIUM (visual bugs degrade UX)
**Fix approach:** Set up React Testing Library. Test:
  - Price flash animation triggers on price change
  - Watchlist renders correctly with prices
  - Chat message sends and response displays
  - EventSource reconnection after disconnect
  - Portfolio charts render with correct data

### No Load Testing

**Issue:** Simulator performance under heavy tick volume not tested.
**Files:** No load testing infrastructure
**Impact:** If watchlist grows to 100+ tickers, SSE payload and GBM math could slow down.
**Risk level:** LOW (default 10 tickers)
**Fix approach:** Add locust or k6 load test: simulate 50 tickers, 100 concurrent SSE clients, sustained for 5 minutes. Monitor memory and latency.

---

## Missing Features Blocking MVP

### Portfolio P&L Calculation Not Yet Implemented

**Issue:** `PriceCache` has prices, but no module calculates unrealized/realized P&L.
**Files:** Needed in database and API layer (not yet created)
**Impact:** Cannot show P&L chart or heatmap. Core feature missing.
**Fix approach:** Implement in portfolio service:
  - Unrealized P&L = (current_price - avg_cost) * quantity
  - Total portfolio value = sum(current_price * quantity) + cash_balance
  - Portfolio snapshots recorded every 30s and after each trade

### Trade Execution Logic Not Implemented

**Issue:** No module handles buy/sell order validation and execution.
**Files:** Needed in API and database layer (not yet created)
**Impact:** Frontend buy/sell buttons do nothing.
**Fix approach:** Implement in trade service:
  - Buy: sufficient cash? update position avg_cost, record trade, update portfolio snapshot
  - Sell: sufficient shares? compute realized P&L, record trade, update cash, update portfolio snapshot
  - Handle fractional shares and rounding

### Watchlist Management Not Implemented

**Issue:** No add/remove endpoints.
**Files:** `/api/watchlist` endpoints needed
**Impact:** User cannot customize watchlist beyond default 10 tickers.
**Fix approach:** Implement in watchlist service:
  - GET `/api/watchlist` — return list with live prices
  - POST `/api/watchlist` — add ticker, start price streaming
  - DELETE `/api/watchlist/{ticker}` — remove ticker, stop price streaming, remove from cache

### Chat with Auto-Execution Not Implemented

**Issue:** No `/api/chat` endpoint. No structured output parsing. No auto-trade logic.
**Files:** `backend/app/llm/` to be created
**Impact:** Chat panel non-functional.
**Fix approach:** See LLM Integration section above.

---

## Known Fragile Areas (If Implemented)

### Cholesky Decomposition Rebuild in Simulator

**Area:** `GBMSimulator._rebuild_cholesky()` in `backend/app/market/simulator.py` line 154-172
**Files:** `backend/app/market/simulator.py`
**Why fragile:** NumPy Cholesky is sensitive to positive-definite matrices. If correlation coefficients are set incorrectly, `np.linalg.cholesky()` could raise `LinAlgError`.
**Safe modification:**
  - Validate correlation matrix before decomposition
  - Add try/except with fallback to identity matrix (no correlation)
  - Test with edge cases: all tickers same, all uncorrelated, highly correlated pairs

### Timestamp Conversion in Massive API

**Area:** `MassiveDataSource._poll_once()` line 103 in `backend/app/market/massive_client.py`
**Files:** `backend/app/market/massive_client.py`
**Why fragile:** Assumes Massive API timestamps are in milliseconds. If API changes format or returns seconds, conversion breaks silently.
**Safe modification:**
  - Add unit tests that mock Massive API with various timestamp formats
  - Log timestamp before and after conversion
  - Add validation: if timestamp is unreasonable (e.g., year 1970), log warning

### SSE Event Serialization

**Area:** `_generate_events()` in `backend/app/market/stream.py` line 81
**Files:** `backend/app/market/stream.py`
**Why fragile:** Assumes `to_dict()` always succeeds. If `PriceUpdate` model changes, serialization could fail and crash stream.
**Safe modification:**
  - Wrap `to_dict()` in try/except
  - If serialization fails, log error and skip that ticker rather than crashing the stream
  - Add tests for serialization with edge cases: NaN, infinity, very large numbers

---

## Performance Bottlenecks

### GBM Simulator Step Performance

**Concern:** `step()` method (line 74-118 in `simulator.py`) is called every 500ms for 10 tickers. With 100+ tickers, NumPy matrix operations could become slow.
**Current:** ~10 tickers × 2 ticks/sec = 20 price updates/sec. Matrix multiply is O(n) where n=10, negligible.
**Future risk:** If watchlist grows to 100+ tickers, O(n) becomes O(100) — still fast, but memory usage for Cholesky matrix grows O(n²).
**Mitigation:** Monitor performance with load test (see Test Coverage Gaps section). If needed, consider lazy Cholesky updates or sampling uncorrelated tickers.

### Database Query Performance

**Concern:** Once database layer is added, queries on `positions` and `trades` without indexes could be slow.
**Risk level:** LOW (single user, small datasets)
**Mitigation:** Index `(user_id, ticker)` on `positions` and `(user_id, created_at DESC)` on `trades` for history sorting.

---

## Recommendations by Priority

| Priority | Area | Action |
|----------|------|--------|
| **CRITICAL** | Frontend | Create empty Next.js project structure, establish CI/CD for frontend builds |
| **CRITICAL** | FastAPI app | Create main app with router mounting, DB initialization, SSE streaming |
| **CRITICAL** | Database | Add SQLite schema, models, initialization; seed default user and watchlist |
| **CRITICAL** | API endpoints | Implement portfolio, watchlist, chat, health routes |
| **CRITICAL** | LLM integration | Add LiteLLM client, structured output parsing, trade validation |
| **HIGH** | Docker | Create Dockerfile, docker-compose, start/stop scripts; test build locally |
| **HIGH** | Environment | Create `.env.example`, document all vars, add validation on startup |
| **HIGH** | Tests | Add API unit tests, database tests, E2E tests for critical flows |
| **MEDIUM** | Error handling | Implement comprehensive error handling, user-facing error messages |
| **MEDIUM** | Rate limiting | Add rate limiter to chat endpoint; document quota |
| **MEDIUM** | Performance | Establish baseline metrics (startup time, memory, request latency); monitor |
| **LOW** | Scaling | Document path to multi-user (auth, connection pooling, PostgreSQL) |

---

*Concerns audit: 2026-07-04*
