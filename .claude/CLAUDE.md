<!-- GSD:project-start source:PROJECT.md -->

## Project

**FinAlly — AI Trading Workstation**

FinAlly (Finance Ally) is a visually stunning, AI-powered trading workstation that streams live market data, lets a user trade a simulated $10,000 portfolio, and embeds an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot. It is the capstone project for an agentic AI coding course — built entirely by orchestrated coding agents to demonstrate production-quality full-stack output. Single user, no auth, runs from one Docker command on `http://localhost:8000`.

**Core Value:** The user watches live prices stream and can trade — manually or by asking the AI — with the portfolio, positions, and P&L updating instantly. If everything else fails, live price streaming + trade execution + a working AI chat that can act on the portfolio must work.

### Constraints

- **Tech stack**: FastAPI (uv) backend + Next.js static export frontend, served single-origin on port 8000 — no CORS. Rationale: one container, one port, students run one command.
- **Database**: SQLite at `db/finally.db`, lazy-initialized, volume-mounted. Rationale: no auth → no multi-user → no DB server needed.
- **Real-time**: SSE via native `EventSource`. Rationale: one-way push, universal browser support, simpler than WebSockets.
- **LLM**: LiteLLM → OpenRouter (Cerebras) with structured outputs, via `cerebras-inference` skill. Rationale: fast inference, reliable trade-intent parsing.
- **Market data**: env-driven (simulator default, Massive if key present). Rationale: works with zero external dependencies out of the box.
- **Deployment**: single multi-stage Docker container. Rationale: reproducible one-command launch for students.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.12+ - Backend (FastAPI, market data, LLM integration)
- TypeScript - Frontend (planned; not yet implemented)
- JavaScript - Frontend build system (Next.js, node dependencies)

## Runtime

- Python 3.12 runtime
- Node.js 20 (for frontend builds, per Dockerfile specification in PLAN.md)
- uv (for Python dependencies)
- npm/node (for frontend, not yet configured)

## Frameworks

- FastAPI 0.128.7 - Web framework for REST/SSE APIs, serving static files
- Uvicorn 0.40.0 - ASGI server, runs on port 8000
- Starlette 0.40.6 - HTTP toolkit underlying FastAPI
- Next.js - Frontend framework (planned, static export mode with TypeScript, not yet scaffolded)
- Pydantic 2.12.5 - Data validation, structured JSON serialization
- pytest 9.0.2 - Test runner
- pytest-asyncio 1.3.0 - Async test support
- pytest-cov 7.0.0 - Coverage reporting
- hatchling - Python build backend
- Ruff 0.15.0 - Linter and formatter
- python-dotenv 1.2.1 - Environment variable loading

## Key Dependencies

- massive 2.2.0 - Polygon.io REST API client for real market data
- numpy 2.4.2 - Numerical computing for GBM (Geometric Brownian Motion) simulator
- rich 14.3.2 - Terminal UI library
- httptools 0.7.1 - C-accelerated HTTP parsing (via Uvicorn)
- anyio 4.12.1 - Async I/O abstraction
- certifi 2026.1.4 - SSL certificates for HTTPS validation
- idna 3.11 - International domain names

## Configuration

- .env file (not committed; .env.example to be provided)
- Three key environment variables:
- pyproject.toml at `backend/pyproject.toml` - Project metadata, dependencies, tool config
- pytest config: defined in `backend/pyproject.toml` under `[tool.pytest.ini_options]`
- ruff config: defined in `backend/pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`
- Python version constraint: `requires-python = ">=3.12"`

## Platform Requirements

- Python 3.12+
- uv package manager
- Docker (for container builds, scripts not yet implemented)
- Docker container
- Port 8000 exposed
- SQLite database file persisted via Docker volume mount at `/app/db/finally.db`
- Environment variables provided via `.env` file passed to container

## Architecture Notes

- FastAPI serves both `/api/*` REST endpoints and `/api/stream/*` SSE streaming
- Static frontend assets served from `/` by FastAPI (Next.js static export when ready)
- SQLite database initialized lazily on first request (no migration step)
- Background market data task runs in-process (simulator or Massive poller)
- Market data subsystem: `from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source, create_stream_router`
- Located in `backend/app/market/` with public API in `__init__.py`

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- snake_case throughout
- Example: `simulator.py`, `price_cache.py`, `massive_client.py`
- Test files: `test_*.py` (e.g., `test_models.py`, `test_simulator_source.py`)
- PascalCase (CapWords)
- Example: `GBMSimulator`, `PriceCache`, `MarketDataSource`, `MassiveDataSource`
- Abstract base classes: `MarketDataSource` (inherits from ABC)
- snake_case
- Public: `get_price()`, `add_ticker()`, `update()`, `create_market_data_source()`
- Private (prefixed with `_`): `_add_ticker_internal()`, `_rebuild_cholesky()`, `_poll_once()`, `_generate_events()`
- Static methods: decorated with `@staticmethod` (e.g., `_pairwise_correlation()`)
- snake_case
- Private instance attributes: `_prices`, `_cache`, `_task`, `_api_key`, `_tickers`
- Protected by convention (not Python-enforced)
- UPPER_SNAKE_CASE
- Example: `DEFAULT_DT`, `TRADING_SECONDS_PER_YEAR`, `SEED_PRICES`, `CORRELATION_GROUPS`
- Defined in module-level constants file: `app/market/seed_prices.py`

## Code Style

- **Ruff** for linting and style checking
- Configuration: `pyproject.toml` [tool.ruff]
- Line length: 100 characters (E501 ignored)
- Python target: 3.12+
- E: pycodestyle errors
- F: Pyflakes (undefined names, unused imports)
- I: isort (import ordering)
- N: pep8-naming (naming conventions)
- W: pycodestyle warnings
- Python 3.10+ union syntax: `str | None` instead of `Optional[str]`
- Full type hints on function signatures
- Return type hints always specified
- Use `from __future__ import annotations` for forward references
- Frozen dataclasses for immutable data
- Use `slots=True` for memory efficiency
- Example from `app/market/models.py`:

## Import Organization

- Use relative imports within packages: `from .cache import PriceCache`
- Module logger: `logger = logging.getLogger(__name__)` at module level
- Explicit `__all__` in `__init__.py` files with docstring

## Error Handling

- Network errors in polling loops: catch, log warning, continue
- Missing attributes in parsed data: catch, log warning, skip record
- Configuration errors at startup: let fail (fatal)
- API key invalid: catch, log error, disable feature
- `logger.debug()`: Algorithm details, state changes (e.g., random events)
- `logger.info()`: Lifecycle events (component start/stop), important state
- `logger.warning()`: Recoverable errors (missing data, skipped items)
- `logger.error()`: Serious issues (API failures, unexpected exceptions)

## Logging

- Component lifecycle: `logger.info("Started", extra_context)`
- Recoverable errors: `logger.warning()`
- Fatal errors: `logger.error()`
- Algorithm details (correlated moves, random events): `logger.debug()`
- API keys, secrets (never include in error messages)
- Excessive data (don't dump full dicts/lists)

## Comments

- Algorithm explanation (math formulas, correlation logic)
- Non-obvious design decisions
- Workarounds or known limitations
- Example from `app/market/simulator.py`:
- Module docstring at the top of every file
- Class docstring explaining purpose and usage
- Method/function docstring with brief description
- Include lifecycle details for complex components
- Use for complex data flows or algorithms
- Example from `app/market/simulator.py`:

## Function Design

- Type-annotated
- Use default values for optional parameters
- Avoid global state / use dependency injection
- Always type-annotated
- Return early with guard clauses to reduce nesting
- Return `None` explicitly for "no result" cases
- Prefix task names for clarity: `asyncio.create_task(self._poll_loop(), name="massive-poller")`
- Use `asyncio.to_thread()` to run sync code without blocking: `snapshots = await asyncio.to_thread(self._fetch_snapshots)`
- Proper cleanup: `try/finally` with `task.cancel()` and `await task`

## Module Design

- Always define `__all__` in `__init__.py`
- Include docstring listing public API (types, functions)
- Example from `app/market/__init__.py`:
- Use `create_*` functions for dependency injection
- Avoids global state and singletons
- Example: `create_market_data_source()`, `create_stream_router()`
- Abstract base classes for pluggable implementations
- Example: `MarketDataSource` (abstract) → `SimulatorDataSource`, `MassiveDataSource` (concrete)
- Document shared mutable state
- Use `threading.Lock()` for critical sections
- Example from `app/market/cache.py`:

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- **Dependency Injection** — `PriceCache` is passed to both data sources; sources write to it, consumers read from it. No global state.
- **Background Tasks** — Both `SimulatorDataSource` and `MassiveDataSource` run async `asyncio.Task` loops that periodically write to the cache without blocking the event loop.
- **Thread-Safe Cache** — `PriceCache` uses a `threading.Lock` to protect concurrent reads from SSE clients and writes from the data source task.
- **Factory Selection** — Environment variable controls which data source is instantiated; downstream code never knows or cares which implementation is running.
- **Immutable Models** — `PriceUpdate` is a frozen dataclass; price history is implicit (only current + previous are stored, plus metadata for direction).

## Layers

- **Purpose:** Generate or fetch price updates for a set of tickers
- **Location:** `app/market/simulator.py`, `app/market/massive_client.py`
- **Contains:** Async background tasks, external API calls (Massive) or mathematical simulation (GBM)
- **Depends on:** `PriceCache`, numpy (simulator only), massive SDK (Massive only)
- **Used by:** Application startup, ticker watchlist management
- **Purpose:** Thread-safe, in-memory storage of the latest price state
- **Location:** `app/market/cache.py`
- **Contains:** `PriceCache` class, write operations (update), read operations (get, get_all), lifecycle helpers
- **Depends on:** `threading.Lock` (standard library)
- **Used by:** Data source write path, SSE streaming, (future) portfolio valuation
- **Purpose:** Push price updates to connected clients in real-time via Server-Sent Events
- **Location:** `app/market/stream.py`
- **Contains:** FastAPI route factory, async event generator, JSON serialization
- **Depends on:** `PriceCache` (read-only), `fastapi.Response`
- **Used by:** Frontend clients via browser `EventSource` API

## Data Flow

### Primary Request Path: SSE Price Stream

### Data Source Initialization

- **Mutable state:** `PriceCache._prices` dict (protected by lock), data source `_task` reference
- **Immutable state:** Each `PriceUpdate` is frozen; history implicit (only current + previous stored)
- **Shared state:** Cache is passed by reference to all consumers; no copying

## Key Abstractions

- **Purpose:** Represent a single ticker's price at a point in time, with computed direction/change metadata
- **Examples:** `app/market/models.py:PriceUpdate`
- **Pattern:** Frozen dataclass (immutable); properties compute direction and change percent on-the-fly
- **Serialization:** `to_dict()` method for JSON transmission
- **Purpose:** Abstract contract for price providers
- **Examples:** `app/market/simulator.py:SimulatorDataSource`, `app/market/massive_client.py:MassiveDataSource`
- **Pattern:** ABC (Abstract Base Class); implementations override `start()`, `stop()`, `add_ticker()`, `remove_ticker()`
- **Lifecycle:** One-shot `start()`, zero or more `add_ticker()`/`remove_ticker()` calls, one-shot `stop()`
- **Purpose:** Thread-safe in-memory store, version counter for change detection
- **Pattern:** Lock-protected dict; monotonic version counter bumped on every `update()`
- **API:** `update()` (write), `get()`, `get_all()`, `remove()` (reads)
- **Purpose:** Geometric Brownian Motion math engine with correlated ticker moves
- **Pattern:** Pure simulator (no async, no I/O); called from `SimulatorDataSource._run_loop()`
- **Math:** Cholesky decomposition of correlation matrix to generate correlated normal random variables

## Entry Points

- **Location:** Application startup code (not yet written; expected in `app/__init__.py` or `app/main.py`)
- **Triggers:** Server startup
- **Responsibilities:** Call `create_market_data_source()`, instantiate SSE router, await `source.start(default_tickers)`
- **Location:** `app/market/stream.py:stream_prices()` (line 27, FastAPI route `/api/stream/prices`)
- **Triggers:** Browser `EventSource` connection
- **Responsibilities:** Serve price updates as text/event-stream, detect client disconnect, stop yielding
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

### No Global PriceCache Singleton

### No Synchronous Blocking in Async Loop

## Error Handling

- **Simulator step failure:** Logged via `logger.exception()`, loop continues on next interval (`simulator.py` line 269)
- **Massive API failure:** Logged as warning/error, poll retries on next interval without blocking the event loop (`massive_client.py` lines 118–121)
- **SSE client disconnect:** Detected via `request.is_disconnected()`, generator stops cleanly (`stream.py` line 71)

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| cerebras-inference | Use this to write code to call an LLM using LiteLLM and OpenRouter with the Cerebras inference provider | `.claude/skills/cerebras/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
