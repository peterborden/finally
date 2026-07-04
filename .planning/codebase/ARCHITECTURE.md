# Architecture

**Analysis Date:** 2026-07-04

## System Overview

The FinAlly backend is a Python/FastAPI application implementing a real-time market data subsystem. The architecture separates concerns into three layers: **data sources** (pluggable implementations), a **shared price cache** (thread-safe in-memory store), and **consumers** (SSE streaming, future portfolio/trading logic).

```text
┌─────────────────────────────────────────────────────────────┐
│                    Consumers                                 │
│  ┌──────────────────┬──────────────────┬──────────────────┐ │
│  │  SSE Streaming   │  Portfolio API   │  Chat/Trading    │ │
│  │  `/api/stream`   │  (future)        │  (future)        │ │
│  └──────────────────┴──────────────────┴──────────────────┘ │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          Shared Price Cache (Thread-Safe)                    │
│          `app/market/cache.py:PriceCache`                    │
│  Holds: Latest price + previous_price + timestamp per ticker │
│  Version counter for change detection                        │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               Market Data Sources (Pluggable)                │
│  Abstract: `app/market/interface.py:MarketDataSource`        │
│  ┌──────────────────────────┬───────────────────────────┐   │
│  │ SimulatorDataSource      │ MassiveDataSource         │   │
│  │ `simulator.py`           │ `massive_client.py`       │   │
│  │ GBM correlated moves     │ Polygon.io REST API       │   │
│  │ In-process background    │ Async polling loop        │   │
│  │ task every 500ms         │ 15s interval (free tier)  │   │
│  └──────────────────────────┴───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **PriceCache** | Thread-safe store of latest prices, direction tracking, version counter | `app/market/cache.py` |
| **PriceUpdate** | Immutable snapshot: ticker, price, previous_price, timestamp, computed properties (change, change_percent, direction) | `app/market/models.py` |
| **MarketDataSource** | Abstract interface defining lifecycle: start(), stop(), add_ticker(), remove_ticker() | `app/market/interface.py` |
| **SimulatorDataSource** | Geometric Brownian Motion (GBM) price simulator with correlated moves and random events | `app/market/simulator.py` |
| **GBMSimulator** | Core math engine: generates correlated random walks using Cholesky decomposition | `app/market/simulator.py` |
| **MassiveDataSource** | Massive/Polygon.io REST API client, polling loop, response parsing | `app/market/massive_client.py` |
| **SSE Router** | FastAPI route factory creating `/api/stream/prices` Server-Sent Events endpoint | `app/market/stream.py` |
| **Factory** | Selects data source (Massive if `MASSIVE_API_KEY` set, else Simulator) | `app/market/factory.py` |
| **Seed Data** | Default tickers, initial prices, per-ticker GBM parameters, correlation groups | `app/market/seed_prices.py` |

## Pattern Overview

**Overall:** Factory + Abstract Interface + Pluggable Implementations

**Key Characteristics:**
- **Dependency Injection** — `PriceCache` is passed to both data sources; sources write to it, consumers read from it. No global state.
- **Background Tasks** — Both `SimulatorDataSource` and `MassiveDataSource` run async `asyncio.Task` loops that periodically write to the cache without blocking the event loop.
- **Thread-Safe Cache** — `PriceCache` uses a `threading.Lock` to protect concurrent reads from SSE clients and writes from the data source task.
- **Factory Selection** — Environment variable controls which data source is instantiated; downstream code never knows or cares which implementation is running.
- **Immutable Models** — `PriceUpdate` is a frozen dataclass; price history is implicit (only current + previous are stored, plus metadata for direction).

## Layers

**Market Data Source Layer:**
- **Purpose:** Generate or fetch price updates for a set of tickers
- **Location:** `app/market/simulator.py`, `app/market/massive_client.py`
- **Contains:** Async background tasks, external API calls (Massive) or mathematical simulation (GBM)
- **Depends on:** `PriceCache`, numpy (simulator only), massive SDK (Massive only)
- **Used by:** Application startup, ticker watchlist management

**Cache Layer:**
- **Purpose:** Thread-safe, in-memory storage of the latest price state
- **Location:** `app/market/cache.py`
- **Contains:** `PriceCache` class, write operations (update), read operations (get, get_all), lifecycle helpers
- **Depends on:** `threading.Lock` (standard library)
- **Used by:** Data source write path, SSE streaming, (future) portfolio valuation

**Consumer Layer (SSE Streaming):**
- **Purpose:** Push price updates to connected clients in real-time via Server-Sent Events
- **Location:** `app/market/stream.py`
- **Contains:** FastAPI route factory, async event generator, JSON serialization
- **Depends on:** `PriceCache` (read-only), `fastapi.Response`
- **Used by:** Frontend clients via browser `EventSource` API

## Data Flow

### Primary Request Path: SSE Price Stream

1. **Client connects** → `GET /api/stream/prices` (`app/market/stream.py:stream_prices()` line 27)
2. **Stream generator begins** → `_generate_events()` polls cache version and yields SSE data (`stream.py` line 51)
3. **Background task writes** → Data source (simulator or Massive) calls `cache.update()` every 500ms/15s
4. **Generator detects change** → Version counter increments; if changed, JSON-serialize all prices and yield event
5. **Browser receives event** → Client-side `EventSource` parses and updates UI

### Data Source Initialization

1. **App startup** → `create_market_data_source()` checks `MASSIVE_API_KEY` environment variable
2. **Factory returns source** → `SimulatorDataSource` or `MassiveDataSource` instance
3. **Caller awaits `source.start(tickers)`** → Creates background task, seeds cache with initial prices
4. **Background loop begins** → Simulator calls `step()` every 500ms; Massive polls every 15s (free tier)
5. **Prices flow into cache** → Each update increments version counter

**State Management:**
- **Mutable state:** `PriceCache._prices` dict (protected by lock), data source `_task` reference
- **Immutable state:** Each `PriceUpdate` is frozen; history implicit (only current + previous stored)
- **Shared state:** Cache is passed by reference to all consumers; no copying

## Key Abstractions

**PriceUpdate:**
- **Purpose:** Represent a single ticker's price at a point in time, with computed direction/change metadata
- **Examples:** `app/market/models.py:PriceUpdate`
- **Pattern:** Frozen dataclass (immutable); properties compute direction and change percent on-the-fly
- **Serialization:** `to_dict()` method for JSON transmission

**MarketDataSource:**
- **Purpose:** Abstract contract for price providers
- **Examples:** `app/market/simulator.py:SimulatorDataSource`, `app/market/massive_client.py:MassiveDataSource`
- **Pattern:** ABC (Abstract Base Class); implementations override `start()`, `stop()`, `add_ticker()`, `remove_ticker()`
- **Lifecycle:** One-shot `start()`, zero or more `add_ticker()`/`remove_ticker()` calls, one-shot `stop()`

**PriceCache:**
- **Purpose:** Thread-safe in-memory store, version counter for change detection
- **Pattern:** Lock-protected dict; monotonic version counter bumped on every `update()`
- **API:** `update()` (write), `get()`, `get_all()`, `remove()` (reads)

**GBMSimulator:**
- **Purpose:** Geometric Brownian Motion math engine with correlated ticker moves
- **Pattern:** Pure simulator (no async, no I/O); called from `SimulatorDataSource._run_loop()`
- **Math:** Cholesky decomposition of correlation matrix to generate correlated normal random variables

## Entry Points

**Market Data Subsystem Start:**
- **Location:** Application startup code (not yet written; expected in `app/__init__.py` or `app/main.py`)
- **Triggers:** Server startup
- **Responsibilities:** Call `create_market_data_source()`, instantiate SSE router, await `source.start(default_tickers)`

**SSE Endpoint:**
- **Location:** `app/market/stream.py:stream_prices()` (line 27, FastAPI route `/api/stream/prices`)
- **Triggers:** Browser `EventSource` connection
- **Responsibilities:** Serve price updates as text/event-stream, detect client disconnect, stop yielding

**Ticker Management (Future):**
- **Expected Location:** `app/portfolio.py` or similar (not yet written)
- **Triggers:** User adds/removes ticker from watchlist, or LLM chat changes watchlist
- **Responsibilities:** Call `source.add_ticker()`, `source.remove_ticker()`, update database

## Architectural Constraints

- **Threading:** Single-threaded event loop (async) with one background task per data source. `PriceCache` uses `threading.Lock` to protect dict access from event loop and potential background futures.
- **Global state:** None. All state is injected (PriceCache passed to sources/consumers).
- **Circular imports:** None detected. Clear dependency order: models → cache → interface → implementations → factory → consumers.
- **Synchronous calls in async context:** `MassiveDataSource` uses `asyncio.to_thread()` to run the synchronous Massive SDK call in a thread pool without blocking the event loop (`massive_client.py` line 97).

## Anti-Patterns

### No Direct Data Source Access by Consumers

**What happens:** All consumers (SSE, portfolio, trading) read only from `PriceCache`, never call the data source directly.

**Why it's wrong:** Would create tight coupling and require knowledge of data source type; would bypass the price cache, causing multiple API calls or multiple simulations.

**Do this instead:** Read from `PriceCache`. Cache is the single source of truth. (`app/market/cache.py`)

### No Global PriceCache Singleton

**What happens:** `PriceCache` is instantiated once and injected into all components.

**Why it's wrong:** Global state is hard to test and makes dependency graph implicit.

**Do this instead:** Dependency injection pattern. Pass `price_cache` parameter to `create_market_data_source()` and SSE router factory. (`app/market/factory.py`, `app/market/stream.py`)

### No Synchronous Blocking in Async Loop

**What happens:** Massive API client uses `asyncio.to_thread()` to offload sync I/O.

**Why it's wrong:** Calling sync I/O directly in async context blocks the event loop and starves other async tasks.

**Do this instead:** Wrap sync calls with `asyncio.to_thread()` or use an async library. (`massive_client.py` line 97)

## Error Handling

**Strategy:** Failures in data sources are logged but do not crash the system. SSE keeps streaming; users see the last known prices until the source recovers.

**Patterns:**
- **Simulator step failure:** Logged via `logger.exception()`, loop continues on next interval (`simulator.py` line 269)
- **Massive API failure:** Logged as warning/error, poll retries on next interval without blocking the event loop (`massive_client.py` lines 118–121)
- **SSE client disconnect:** Detected via `request.is_disconnected()`, generator stops cleanly (`stream.py` line 71)

## Cross-Cutting Concerns

**Logging:** Uses Python standard `logging` module. Module-level loggers created with `__name__`. Log level configurable via environment (future: add DEBUG env var support).

**Validation:** Ticker symbols normalized to uppercase; prices rounded to 2 decimals in cache to prevent floating-point precision issues. No schema validation library used (could add Pydantic in future).

**Authentication:** Not applicable for this subsystem. Will be handled at API layer (future `/api/` endpoints will authenticate against database).

---

*Architecture analysis: 2026-07-04*
