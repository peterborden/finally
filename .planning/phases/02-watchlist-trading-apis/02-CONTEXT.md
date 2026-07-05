# Phase 2: Watchlist & Trading APIs - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

REST endpoints for watchlist management and simulated portfolio trading, backed by live prices from the shared `PriceCache` (on `app.state`). Requirements: WATCH-01, WATCH-02, WATCH-03, PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, PORT-06.

Endpoints (PLAN.md §8):
- GET /api/watchlist — watched tickers with latest prices
- POST /api/watchlist {ticker} — add ticker (also add to market source so it streams)
- DELETE /api/watchlist/{ticker} — remove ticker (also remove from market source)
- GET /api/portfolio — positions, cash, total value, unrealized P&L
- POST /api/portfolio/trade {ticker, quantity, side} — market order, instant fill at current price
- GET /api/portfolio/history — portfolio_snapshots over time

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices at Claude's discretion (discuss skipped). Follow PLAN.md §7 (schema) and §8 (endpoints). Build on Phase 1's app: reuse `app.db` connection/init helpers and the `PriceCache` stored on `app.state`. Read live prices from the cache (never the data source directly — see codebase ARCHITECTURE.md anti-patterns). Wire watchlist add/remove to the market source's `add_ticker`/`remove_ticker` (available via the running source; store a reference on `app.state` in the lifespan if not already).

Trade execution semantics (PLAN.md §2, §7):
- Market orders only, instant fill at the current cached price, no fees, no confirmation.
- Fractional shares supported (quantity REAL).
- Buy: require cash_balance >= quantity*price, else reject with clear error, portfolio unchanged. On success: decrement cash, upsert position with new average cost = (old_qty*old_avg + qty*price)/(old_qty+qty), append trade row, snapshot portfolio.
- Sell: require existing position quantity >= quantity, else reject. On success: increment cash, decrement/remove position (remove row when quantity hits ~0), append trade row, snapshot portfolio.
- Unrealized P&L per position = (current_price - avg_cost) * quantity; % change = (current_price/avg_cost - 1).
- Total value = cash + sum(position.quantity * current_price).

Snapshots (PORT-06): a background asyncio task records a portfolio_snapshots row every 30s, AND a snapshot is written immediately after each trade. Start the snapshot task in the app lifespan.

Use Pydantic models for request/response validation. Organize as a portfolio/watchlist service module + FastAPI routers (e.g. app/portfolio.py, app/watchlist.py or app/routes/). Keep DB access parameterized; reuse Phase 1 connection helper.

</decisions>

<code_context>
## Existing Code Insights

Phase 1 built: app/main.py (create_app, lifespan starting market source + SSE + snapshot-ready app.state), app/db/ (schema, connection, seed, init_database), app/static/, tests via FastAPI TestClient. PriceCache is on app.state; the market source instance should be reachable for add/remove ticker (confirm/expose it in the lifespan). Codebase context gathered during planning.

</code_context>

<specifics>
## Specific Ideas

Schema fields exact per PLAN.md §7 (positions, trades, portfolio_snapshots already created in Phase 1). Validation errors should return appropriate HTTP status (e.g. 400/422) with a descriptive message so the frontend and AI chat (Phase 3) can surface them.

</specifics>

<deferred>
## Deferred Ideas

None — discuss skipped. Limit orders, fees, order book are Out of Scope per REQUIREMENTS.md.

</deferred>
