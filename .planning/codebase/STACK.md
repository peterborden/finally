# Technology Stack

**Analysis Date:** 2026-07-04

## Languages

**Primary:**
- Python 3.12+ - Backend (FastAPI, market data, LLM integration)

**Secondary:**
- TypeScript - Frontend (planned; not yet implemented)
- JavaScript - Frontend build system (Next.js, node dependencies)

## Runtime

**Environment:**
- Python 3.12 runtime
- Node.js 20 (for frontend builds, per Dockerfile specification in PLAN.md)

**Package Manager:**
- uv (for Python dependencies)
  - Lockfile: `backend/uv.lock` (present)
- npm/node (for frontend, not yet configured)

## Frameworks

**Core:**
- FastAPI 0.128.7 - Web framework for REST/SSE APIs, serving static files
- Uvicorn 0.40.0 - ASGI server, runs on port 8000
- Starlette 0.40.6 - HTTP toolkit underlying FastAPI
- Next.js - Frontend framework (planned, static export mode with TypeScript, not yet scaffolded)

**Data Validation & Serialization:**
- Pydantic 2.12.5 - Data validation, structured JSON serialization

**Testing:**
- pytest 9.0.2 - Test runner
- pytest-asyncio 1.3.0 - Async test support
- pytest-cov 7.0.0 - Coverage reporting

**Build/Dev:**
- hatchling - Python build backend
- Ruff 0.15.0 - Linter and formatter
- python-dotenv 1.2.1 - Environment variable loading

## Key Dependencies

**Critical:**
- massive 2.2.0 - Polygon.io REST API client for real market data
  - Enables optional integration with live stock market data
  - Used in `app/market/massive_client.py` for polling snapshots
- numpy 2.4.2 - Numerical computing for GBM (Geometric Brownian Motion) simulator
  - Used in `app/market/simulator.py` for correlated price generation
  - Cholesky decomposition for ticker correlations

**Infrastructure:**
- rich 14.3.2 - Terminal UI library
  - Used in `market_data_demo.py` for dashboard rendering
  - Not used in production API layer

**HTTP/Network:**
- httptools 0.7.1 - C-accelerated HTTP parsing (via Uvicorn)
- anyio 4.12.1 - Async I/O abstraction
- certifi 2026.1.4 - SSL certificates for HTTPS validation
- idna 3.11 - International domain names

## Configuration

**Environment:**
- .env file (not committed; .env.example to be provided)
- Three key environment variables:
  - `OPENROUTER_API_KEY` - Required for LLM chat functionality
  - `MASSIVE_API_KEY` - Optional; enables real market data via Polygon.io
  - `LLM_MOCK` - Optional; set to `"true"` for deterministic mock responses (E2E testing)

**Build:**
- pyproject.toml at `backend/pyproject.toml` - Project metadata, dependencies, tool config
- pytest config: defined in `backend/pyproject.toml` under `[tool.pytest.ini_options]`
- ruff config: defined in `backend/pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`
- Python version constraint: `requires-python = ">=3.12"`

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- Docker (for container builds, scripts not yet implemented)

**Production:**
- Docker container
- Port 8000 exposed
- SQLite database file persisted via Docker volume mount at `/app/db/finally.db`
- Environment variables provided via `.env` file passed to container

## Architecture Notes

**Single Container Design:**
- FastAPI serves both `/api/*` REST endpoints and `/api/stream/*` SSE streaming
- Static frontend assets served from `/` by FastAPI (Next.js static export when ready)
- SQLite database initialized lazily on first request (no migration step)
- Background market data task runs in-process (simulator or Massive poller)

**Key Import Paths:**
- Market data subsystem: `from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source, create_stream_router`
- Located in `backend/app/market/` with public API in `__init__.py`

---

*Stack analysis: 2026-07-04*
