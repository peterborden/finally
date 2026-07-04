# FinAlly — AI Trading Workstation

## What This Is

FinAlly (Finance Ally) is a visually stunning, AI-powered trading workstation that streams live market data, lets a user trade a simulated $10,000 portfolio, and embeds an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot. It is the capstone project for an agentic AI coding course — built entirely by orchestrated coding agents to demonstrate production-quality full-stack output. Single user, no auth, runs from one Docker command on `http://localhost:8000`.

## Core Value

The user watches live prices stream and can trade — manually or by asking the AI — with the portfolio, positions, and P&L updating instantly. If everything else fails, live price streaming + trade execution + a working AI chat that can act on the portfolio must work.

## Requirements

### Validated

<!-- Shipped and confirmed valuable — the completed market data subsystem (see planning/MARKET_DATA_SUMMARY.md). -->

- ✓ Pluggable market data source behind an abstract interface (simulator + Massive/Polygon.io) selected by env var — existing
- ✓ GBM price simulator with correlated moves, random events, realistic seed prices, ~500ms updates — existing
- ✓ Thread-safe in-memory price cache (latest/previous/timestamp/version) shared across consumers — existing
- ✓ SSE streaming endpoint `GET /api/stream/prices` with change detection and clean disconnect handling — existing
- ✓ Factory selection (Massive if `MASSIVE_API_KEY` set, else simulator) — existing
- ✓ Unit/integration test suite for the market subsystem (pytest + pytest-asyncio) — existing

### Active

<!-- Current scope. Hypotheses until shipped and validated. -->

**Backend — App & Persistence**
- [ ] FastAPI application assembly (`app/main.py`): startup wires market data source + SSE router, serves static frontend, `/api/health`
- [ ] SQLite database with lazy initialization (create schema + seed default data on first request if absent)
- [ ] Schema: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages` (all with `user_id` default `"default"`)
- [ ] Default seed: profile with $10,000 cash; 10-ticker watchlist (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX)

**Backend — Portfolio & Trading**
- [ ] `GET /api/portfolio` — positions, cash, total value, unrealized P&L
- [ ] `POST /api/portfolio/trade` — market order, instant fill at current price, validation (cash for buys, shares for sells), fractional shares
- [ ] `GET /api/portfolio/history` — portfolio value snapshots for the P&L chart
- [ ] Background task recording `portfolio_snapshots` every 30s and immediately after each trade

**Backend — Watchlist**
- [ ] `GET /api/watchlist` (with latest prices), `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}` — wired to market source add/remove ticker

**Backend — AI Chat**
- [ ] `POST /api/chat` — loads portfolio context + history, calls LLM via LiteLLM→OpenRouter (Cerebras, `openrouter/openai/gpt-oss-120b`) with structured output
- [ ] Auto-execution of LLM-specified trades and watchlist changes (same validation as manual), errors surfaced back into the response
- [ ] `LLM_MOCK=true` deterministic mock mode for E2E/CI
- [ ] Chat history persisted in `chat_messages` (with executed actions JSON)

**Frontend — Next.js Terminal UI (static export)**
- [ ] Dark, data-dense Bloomberg-style layout (Tailwind, custom theme; accent `#ecad0a`, blue `#209dd7`, purple `#753991`)
- [ ] Watchlist grid: price flash green/red on change, daily change %, progressive sparklines accumulated from SSE
- [ ] Main chart area for the selected ticker; click a watchlist ticker to select
- [ ] Portfolio heatmap/treemap (sized by weight, colored by P&L) + P&L line chart over time
- [ ] Positions table (ticker, qty, avg cost, current price, unrealized P&L, % change)
- [ ] Trade bar (ticker, quantity, buy/sell — instant, no confirmation)
- [ ] AI chat panel (collapsible sidebar, loading indicator, inline trade/watchlist confirmations)
- [ ] Header: live total value, cash balance, connection status dot (green/yellow/red)
- [ ] `EventSource` SSE consumption with automatic reconnect

**Delivery**
- [ ] Multi-stage Dockerfile (Node build → Python runtime serving static export + API on port 8000)
- [ ] Start/stop scripts (`start_mac.sh`, `stop_mac.sh`, `start_windows.ps1`, `stop_windows.ps1`), `.env.example`, volume-mounted SQLite
- [ ] Playwright E2E tests in `test/` with `docker-compose.test.yml`, run under `LLM_MOCK=true`

### Out of Scope

- Authentication / multi-user — single-user by design; `user_id` column exists for future multi-user without migration
- Limit orders, order book, partial fills, fees — market orders only, to keep portfolio math simple
- WebSockets — SSE is sufficient for one-way server→client push
- Postgres / external DB server — SQLite file is self-contained, zero-config
- Token-by-token LLM streaming — Cerebras inference is fast enough that a loading indicator suffices
- Trade confirmation dialogs — deliberate design choice; simulated money, fluid agentic demo

## Context

- **Brownfield.** The market data subsystem under `backend/app/market/` is complete and tested; new work builds around it, reading from `PriceCache` (never calling data sources directly — see `.planning/codebase/ARCHITECTURE.md` anti-patterns).
- Backend is a `uv` project (`backend/pyproject.toml`, Python 3.12+, FastAPI/Uvicorn/Pydantic, pytest). Frontend directory exists but is empty — Next.js not yet scaffolded.
- Established conventions: `snake_case` modules, `PascalCase` classes, frozen dataclasses, dependency injection (no globals), `test_<module>.py` mirroring `app/`. See `.planning/codebase/CONVENTIONS.md` and `TESTING.md`.
- LLM integration must use the `cerebras-inference` skill (LiteLLM → OpenRouter → Cerebras, `openrouter/openai/gpt-oss-120b`, structured outputs). `OPENROUTER_API_KEY` is in the project-root `.env`.
- Known concerns catalogued in `.planning/codebase/CONCERNS.md` — consult before touching the market subsystem.

## Constraints

- **Tech stack**: FastAPI (uv) backend + Next.js static export frontend, served single-origin on port 8000 — no CORS. Rationale: one container, one port, students run one command.
- **Database**: SQLite at `db/finally.db`, lazy-initialized, volume-mounted. Rationale: no auth → no multi-user → no DB server needed.
- **Real-time**: SSE via native `EventSource`. Rationale: one-way push, universal browser support, simpler than WebSockets.
- **LLM**: LiteLLM → OpenRouter (Cerebras) with structured outputs, via `cerebras-inference` skill. Rationale: fast inference, reliable trade-intent parsing.
- **Market data**: env-driven (simulator default, Massive if key present). Rationale: works with zero external dependencies out of the box.
- **Deployment**: single multi-stage Docker container. Rationale: reproducible one-command launch for students.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build around the existing `PriceCache`, consumers read-only | Preserve the tested market subsystem's clean architecture | — Pending |
| SQLite lazy-init on first request (no migration step) | Fresh Docker volumes self-seed; zero manual setup | — Pending |
| Auto-execute AI trades with no confirmation | Simulated money; demonstrates agentic capability (course theme) | — Pending |
| Static Next.js export served by FastAPI | Single origin, no CORS, one container | — Pending |
| Market orders only | Eliminates order book / limit logic; simple portfolio math | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-04 after initialization*
