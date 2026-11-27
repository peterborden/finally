# FinAlly Build Contract

The shared contract for the agent team building the rest of FinAlly on top of the
completed market-data subsystem. **This file is the source of truth for module
ownership and cross-module interfaces.** If you need to change an interface defined
here, update this file first and note it in `planning/BUILD_LOG.md` so other agents
see it.

Read `planning/PLAN.md` for the full product spec. Read `planning/MARKET_DATA_SUMMARY.md`
for the finished market-data subsystem you build on.

---

## 1. Module Ownership (do NOT edit files outside your section)

| Owner | Files / dirs | Notes |
|---|---|---|
| **Database eng** | `backend/app/db/**`, `backend/tests/db/**` | Schema, lazy init, seed, repositories |
| **Backend API eng** | `backend/app/main.py`, `backend/app/config.py`, `backend/app/services/**`, `backend/app/api/portfolio.py`, `backend/app/api/watchlist.py`, `backend/app/api/health.py`, `backend/app/api/__init__.py`, `backend/tests/api/**`, `backend/tests/services/**` | App factory, wiring, portfolio/watchlist/trade logic + routes |
| **LLM eng** | `backend/app/llm/**`, `backend/app/api/chat.py`, `backend/tests/llm/**` | Chat endpoint, LiteLLM/Cerebras, structured output, mock mode |
| **Frontend eng** | `frontend/**` | Entire Next.js app (static export) |
| **DevOps eng** | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `scripts/**` | Container + start/stop scripts |
| **Integration tester** | `test/**` | Playwright E2E + `docker-compose.test.yml` |

**Shared files — do not edit concurrently.** `backend/pyproject.toml` deps (`litellm`,
`python-dotenv`, `httpx`) are already added and locked. If you need another dep, add it
and run `uv sync --extra dev`; announce it in `BUILD_LOG.md`. `backend/app/api/__init__.py`
is owned by Backend eng — LLM eng registers `chat.py` via `main.py` wiring that Backend owns
(coordinate through `BUILD_LOG.md`).

---

## 2. Backend module layout (target)

```
backend/app/
├── main.py            [Backend] create_app() factory; lifespan starts market data; registers all routers; serves static frontend
├── config.py          [Backend] loads .env (python-dotenv), exposes settings (LLM_MOCK, OPENROUTER_API_KEY, db path)
├── market/            [DONE] do not modify
├── db/                [Database]
│   ├── __init__.py    exports: init_db, connection, and all repository fns below
│   ├── connection.py  DB path resolution + connection() context manager
│   ├── schema.sql     DDL for the 6 tables in PLAN §7
│   └── repositories.py repository functions (§3)
├── services/          [Backend]
│   ├── portfolio.py   execute_trade(), get_portfolio_state(), record_portfolio_snapshot()
│   └── watchlist.py   add_ticker(), remove_ticker() (DB + market source together)
├── api/
│   ├── portfolio.py   [Backend] router: GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history
│   ├── watchlist.py   [Backend] router: GET/POST/DELETE /api/watchlist
│   ├── health.py      [Backend] router: GET /api/health
│   └── chat.py        [LLM]     router: POST /api/chat
└── llm/               [LLM] client.py, prompt.py, schema.py, mock.py
```

---

## 3. Database repository API  (Database eng OWNS; Backend + LLM CONSUME)

All rows are returned as plain `dict`s (JSON-ready). Timestamps are ISO-8601 UTC strings.
Repositories accept an explicit `sqlite3.Connection` so callers can compose multiple
writes in ONE transaction (required for atomic trade execution).

```python
# backend/app/db/__init__.py must export ALL of the following:

def init_db() -> None
    """Lazy-init: create tables from schema.sql and seed defaults if empty.
    Idempotent; safe to call on every startup. Reads db path from config."""

@contextmanager
def connection() -> Iterator[sqlite3.Connection]
    """Yield a connection with row_factory=sqlite3.Row and foreign_keys ON.
    Commits on clean exit, rolls back on exception. WAL mode enabled."""

# users_profile
def get_profile(conn) -> dict            # {id, cash_balance, created_at}
def set_cash_balance(conn, balance: float) -> None

# watchlist
def get_watchlist(conn) -> list[dict]                 # [{id, ticker, added_at}], insertion order
def add_watchlist_ticker(conn, ticker: str) -> dict   # idempotent; returns the row
def remove_watchlist_ticker(conn, ticker: str) -> bool  # True if a row was deleted

# positions
def get_positions(conn) -> list[dict]                 # [{id, ticker, quantity, avg_cost, updated_at}]
def get_position(conn, ticker: str) -> dict | None
def upsert_position(conn, ticker: str, quantity: float, avg_cost: float) -> dict
def delete_position(conn, ticker: str) -> None

# trades
def record_trade(conn, ticker: str, side: str, quantity: float, price: float) -> dict
    # returns {id, ticker, side, quantity, price, executed_at}
def get_trades(conn, limit: int | None = None) -> list[dict]  # newest first

# portfolio_snapshots
def record_snapshot(conn, total_value: float) -> dict   # {id, total_value, recorded_at}
def get_snapshots(conn, limit: int | None = None) -> list[dict]  # oldest→newest for charting

# chat_messages
def get_recent_messages(conn, limit: int = 20) -> list[dict]  # oldest→newest
def add_message(conn, role: str, content: str, actions: dict | None = None) -> dict
    # actions stored as JSON text; returned parsed back to dict|None
```

Ticker normalization: store/compare tickers **uppercased, stripped**. Seed data and
constraints per PLAN §7 (user_id defaults to `"default"` everywhere).

---

## 4. Service API  (Backend eng OWNS; LLM CONSUMES for chat auto-execution)

The `PriceCache` and `MarketDataSource` singletons live on `app.state` (created in
`main.py` lifespan). Services receive them as parameters — no globals.

```python
# backend/app/services/portfolio.py
from dataclasses import dataclass

@dataclass
class TradeResult:
    success: bool
    error: str | None
    trade: dict | None          # the recorded trade row, if filled
    position: dict | None       # resulting position row (None if fully sold)
    cash_balance: float

def execute_trade(ticker: str, side: str, quantity: float, price_cache) -> TradeResult:
    """Market order, instant fill at current cache price. ONE transaction:
    validate (cash for buy / shares for sell / qty>0 / price available),
    update position (weighted-avg cost on buy), update cash, record trade,
    record a portfolio snapshot. Returns TradeResult; never raises on
    validation failure — sets success=False + error. side in {'buy','sell'}."""

def get_portfolio_state(price_cache) -> dict:
    """Returns the GET /api/portfolio shape (§5.1)."""

def record_portfolio_snapshot(price_cache) -> dict:
    """Compute total value from cash + live position values; persist snapshot."""

# backend/app/services/watchlist.py
def add_ticker(ticker: str, source, price_cache) -> dict:
    """Add to DB watchlist AND source.add_ticker(). Returns watchlist row.
    'source' is the MarketDataSource; call is awaited by the async caller —
    expose an async variant if needed (add_ticker is async on the source)."""
def remove_ticker(ticker: str, source) -> bool:
    """Remove from DB watchlist AND source.remove_ticker()."""
```

> Note: `source.add_ticker/remove_ticker` are **async**. Provide async service
> functions (e.g. `async def add_ticker(...)`) so routers can `await` them. Backend eng
> decides the exact async shape and documents it in `BUILD_LOG.md`.

---

## 5. HTTP API response shapes (Frontend + Integration tester build against these)

All endpoints are same-origin under `/api`. Errors use appropriate 4xx with
`{"detail": "..."}` (FastAPI default) unless noted.

### 5.1 GET /api/portfolio
```json
{
  "cash_balance": 10000.0,
  "positions_value": 1925.0,
  "total_value": 11925.0,
  "total_unrealized_pnl": 25.0,
  "positions": [
    {"ticker":"AAPL","quantity":10,"avg_cost":190.0,"current_price":192.5,
     "market_value":1925.0,"unrealized_pnl":25.0,"unrealized_pnl_percent":1.32}
  ]
}
```
`current_price` may be `null` if the cache has no price yet; downstream treats null as 0 for totals.

### 5.2 POST /api/portfolio/trade
Request: `{"ticker":"AAPL","quantity":10,"side":"buy"}`
Success 200:
```json
{"success":true,"error":null,
 "trade":{"ticker":"AAPL","side":"buy","quantity":10,"price":192.5,"executed_at":"..."},
 "position":{"ticker":"AAPL","quantity":10,"avg_cost":192.5},
 "cash_balance":8075.0}
```
Validation failure 400: `{"detail":"Insufficient cash: need $1925.00, have $100.00"}`.

### 5.3 GET /api/portfolio/history
```json
{"snapshots":[{"total_value":10000.0,"recorded_at":"..."}, ...]}   // oldest→newest
```

### 5.4 GET /api/watchlist
```json
{"watchlist":[
  {"ticker":"AAPL","price":192.5,"previous_price":191.0,"change":1.5,
   "change_percent":0.78,"direction":"up"}
]}
```
Price fields `null` until first tick arrives.

### 5.5 POST /api/watchlist  →  201
Request `{"ticker":"PYPL"}` → returns the same per-item shape as 5.4 (price fields may be null initially).

### 5.6 DELETE /api/watchlist/{ticker}  →  200 `{"removed": true}` (404 if absent)

### 5.7 POST /api/chat
Request `{"message":"buy 5 shares of Apple"}`
Response 200:
```json
{
  "message":"Bought 5 shares of AAPL at $192.50.",
  "trades":[{"ticker":"AAPL","side":"buy","quantity":5,"price":192.5,"executed_at":"..."}],
  "watchlist_changes":[{"ticker":"PYPL","action":"add"}],
  "errors":[]
}
```
`trades`/`watchlist_changes` reflect what was ACTUALLY executed. `errors` lists any
failed actions (e.g. "Insufficient cash for AAPL"). The user + assistant messages are
persisted to `chat_messages` (assistant row carries `actions` JSON).

### 5.8 GET /api/health  →  200 `{"status":"ok"}`

### 5.9 GET /api/stream/prices  →  DONE (SSE). Event data is a JSON object keyed by
ticker: `{"AAPL":{"ticker":"AAPL","price":..,"previous_price":..,"timestamp":..,
"change":..,"change_percent":..,"direction":"up|down|flat"}, ...}`.

---

## 6. LLM structured-output schema (LLM eng)

Per PLAN §9. Response JSON: `{"message": str, "trades":[{ticker,side,quantity}],
"watchlist_changes":[{ticker,action}]}` where action ∈ {add,remove}. Auto-execute each
trade via `services.portfolio.execute_trade` and each watchlist change via
`services.watchlist`. Collect failures into `errors`. Use the **cerebras** skill for the
LiteLLM→OpenRouter call to `openrouter/openai/gpt-oss-120b`. `LLM_MOCK=true` → deterministic
mock (parse simple intents like "buy N TICKER" so E2E can assert a trade appears).

---

## 7. Static serving & port (Backend + DevOps)

`main.py` mounts the built frontend (`backend/static/` inside the container) as the
SPA fallback at `/` AFTER all `/api` routes. Dev: if `backend/static/` is absent, serve a
tiny placeholder or 404 — never crash. App listens on `:8000`. DB file path defaults to
`db/finally.db` relative to project root, overridable via `FINALLY_DB_PATH` (DevOps mounts
`/app/db`). Backend eng defines `config.py`; DevOps reads these names from here.

---

## 8. Coordination protocol

- Append notable decisions / interface changes / "I'm done" to `planning/BUILD_LOG.md`
  (create it; one bullet per entry with your role prefix, e.g. `[DB] ...`).
- Write unit tests for your own code; keep `uv run --extra dev pytest` green.
- Run `uv run --extra dev ruff check app/ tests/` before declaring done.
- Do NOT modify the `market/` package or other owners' files.
