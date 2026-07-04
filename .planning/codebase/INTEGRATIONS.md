# External Integrations

**Analysis Date:** 2026-07-04

## APIs & External Services

**Market Data:**
- **Polygon.io (via Massive SDK)** - Optional real stock market data
  - SDK/Client: `massive` 2.2.0 (REST API client)
  - Auth: `MASSIVE_API_KEY` environment variable
  - Usage: `app/market/massive_client.py` implements `MassiveDataSource`
  - Endpoint: `GET /v2/snapshot/locale/us/markets/stocks/tickers`
  - Rate limits: Free tier (5 req/min, poll every 15s), paid tiers (higher frequency)
  - Behavior: Not used if `MASSIVE_API_KEY` is absent or empty; defaults to simulator

**LLM Integration:**
- **OpenRouter** - AI chat assistant and trade execution
  - SDK/Client: LiteLLM (not yet vendored in dependencies; to be added)
  - Model: `openrouter/openai/gpt-oss-120b` with Cerebras inference provider
  - Auth: `OPENROUTER_API_KEY` environment variable (required)
  - Usage: Structured JSON outputs for trade execution and watchlist changes
  - Behavior: Disabled if `LLM_MOCK=true` (returns deterministic mock responses for testing)
  - Not yet implemented in backend (API route `/api/chat` planned)

## Data Storage

**Databases:**
- **SQLite**
  - Location: `db/finally.db` (runtime path in Docker volume at `/app/db/finally.db`)
  - Client: Python standard library `sqlite3` (used in schema initialization, not yet in implementation)
  - Lazy initialization: Tables created on first request if database doesn't exist
  - Persistence: Docker named volume `finally-data` persists across container restarts

**Schema:**
- `users_profile` - User state (cash balance, timestamps)
- `watchlist` - Ticker tracking (user_id, ticker, added_at)
- `positions` - Current holdings (ticker, quantity, avg_cost)
- `trades` - Trade history append-only log (ticker, side, quantity, price, executed_at)
- `portfolio_snapshots` - Portfolio value over time for P&L charts (total_value, recorded_at)
- `chat_messages` - Conversation history with LLM (role, content, actions as JSON)

**File Storage:**
- Static frontend assets served by FastAPI from built Next.js export
- No external file storage service (S3, etc.) planned

**Caching:**
- In-memory `PriceCache` (`app/market/cache.py`) - Thread-safe, holds latest price for each ticker
- No Redis or external cache service

## Authentication & Identity

**Auth Provider:**
- None - Single-user application (no login/signup)
- Hardcoded default user: `user_id="default"` on all database records

**LLM Auth:**
- OpenRouter API key passed via `OPENROUTER_API_KEY` environment variable
- Key used to authenticate calls to OpenRouter proxy service

## Monitoring & Observability

**Error Tracking:**
- None - Application logs to stderr/stdout only
- No integration with Sentry, DataDog, or similar

**Logs:**
- Python logging module with formatters
- Logs written to console (captured by Docker/container runtime)
- Debug logging available (e.g., simulator events in `app/market/simulator.py`)

**Metrics:**
- None - No Prometheus, CloudWatch, or metrics integration

## CI/CD & Deployment

**Hosting:**
- Docker container (single image)
- Port 8000 exposed
- Dockerfile specification in PLAN.md (multi-stage: Node → Python)
- Not yet created in repository

**CI Pipeline:**
- None configured - No GitHub Actions, GitLab CI, or similar

**Container Registry:**
- Not specified; likely Docker Hub or ghcr.io when deployed

**Start/Stop Scripts:**
- `scripts/start_mac.sh` - Launch container (to be implemented)
- `scripts/stop_mac.sh` - Stop container (to be implemented)
- `scripts/start_windows.ps1` - Windows PowerShell equivalent (to be implemented)
- `scripts/stop_windows.ps1` - Windows PowerShell equivalent (to be implemented)

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` - API key for OpenRouter (required for chat functionality)

**Optional env vars:**
- `MASSIVE_API_KEY` - API key for Polygon.io Massive API (optional; uses simulator if absent)
- `LLM_MOCK` - Set to `"true"` for deterministic mock LLM responses (E2E testing only)

**Secrets location:**
- `.env` file in project root (git-ignored)
- `.env.example` to be committed with template/instructions
- Docker `--env-file .env` flag when running container

## Webhooks & Callbacks

**Incoming:**
- None - No webhook listeners configured

**Outgoing:**
- None - No webhook calls made by the application

## Background Tasks

**Market Data Polling:**
- **Simulator (default)**: In-process async task in `SimulatorDataSource`, runs every ~500ms
  - No external API calls
  - Uses numpy for Geometric Brownian Motion calculations
  - Updates `PriceCache` with new prices

- **Massive API (optional)**: In-process async task in `MassiveDataSource`, polls on interval
  - REST API calls to Polygon.io `/v2/snapshot/` endpoint
  - Interval: 15s (free tier) or faster (paid tiers)
  - Updates `PriceCache` from snapshot responses

**Portfolio Snapshots (planned):**
- Background task to record portfolio value snapshots every 30s
- Appends to `portfolio_snapshots` table
- Also triggered immediately after each trade execution

**SSE Streaming:**
- HTTP streaming endpoint at `/api/stream/prices`
- Reads from `PriceCache` every ~500ms
- Long-lived connection; client uses native `EventSource` API
- No authentication

## API Contracts

**Market Data Streaming:**
- `GET /api/stream/prices` - Server-Sent Events (SSE), application/event-stream
- Event format: JSON object keyed by ticker, each value contains price, direction, change, etc.
- Auto-reconnect: retry directive set to 1000ms

**Market Data (planned):**
- `GET /api/stream/prices` - SSE stream of live prices
- `GET /api/watchlist` - List tickers with current prices
- `POST /api/watchlist` - Add ticker: `{ticker}`
- `DELETE /api/watchlist/{ticker}` - Remove ticker

**Portfolio (planned):**
- `GET /api/portfolio` - Positions, cash, total value, unrealized P&L
- `POST /api/portfolio/trade` - Execute trade: `{ticker, quantity, side}`
- `GET /api/portfolio/history` - Portfolio snapshots for P&L chart

**Chat (planned):**
- `POST /api/chat` - Send message: `{message}`
- Response: `{message, trades, watchlist_changes}` (structured JSON)

**Health:**
- `GET /api/health` - Health check (for Docker)

---

*Integration audit: 2026-07-04*
