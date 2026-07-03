<<<<<<< Updated upstream
# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)
=======
# FinAlly — the Finance Ally

An AI-powered trading workstation: a Bloomberg-style terminal that streams live market data, lets you trade a simulated portfolio, and ships with an LLM copilot that can analyze positions and execute trades from natural language.

Built entirely by orchestrated coding agents as the capstone for an agentic AI coding course.

## Features

- **Live price streaming** via SSE, with green/red flash animations and progressive sparklines
- **Simulated portfolio** — start with $10,000, market orders only, instant fills, fractional shares
- **AI chat copilot** — ask about your portfolio and have it execute trades and manage your watchlist
- **Rich visualizations** — detailed charts, a P&L-colored position heatmap, and a portfolio value chart
- **Watchlist management** — add/remove tickers manually or through the AI
- **Zero setup** — no login, no signup; one command and a browser tab

## Architecture

A single Docker container on port `8000`:

- **Frontend** — Next.js + TypeScript, static export, served by FastAPI (Tailwind, dark terminal theme)
- **Backend** — FastAPI (Python, managed with `uv`)
- **Database** — SQLite, lazily initialized and seeded, persisted via a Docker volume
- **Real-time** — Server-Sent Events (`/api/stream/prices`) push price updates to the browser
- **Market data** — built-in GBM simulator by default; real data via the Massive API if a key is provided
- **AI** — LiteLLM → OpenRouter (`openai/gpt-oss-120b` on Cerebras) with structured outputs for trade execution

See [`planning/PLAN.md`](planning/PLAN.md) for the full specification.
>>>>>>> Stashed changes

## Quick Start

```bash
<<<<<<< Updated upstream
# Clone and configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Run with Docker
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally

# Open http://localhost:8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
├── db/          # SQLite volume mount (runtime)
└── scripts/     # Start/stop helpers
```

## License

See [LICENSE](LICENSE).
=======
cp .env.example .env   # add your OPENROUTER_API_KEY
./scripts/start_mac.sh # macOS/Linux  (start_windows.ps1 on Windows)
```

Then open <http://localhost:8000>.

Or run the container directly:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | Enables the LLM chat assistant |
| `MASSIVE_API_KEY` | No | Use real market data; falls back to the simulator if unset |
| `LLM_MOCK` | No | `true` for deterministic mock LLM responses (testing) |

## API

REST and SSE under `/api/*`, all same-origin:

- **Market** — `GET /api/stream/prices`
- **Portfolio** — `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`
- **Watchlist** — `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`
- **Chat** — `POST /api/chat`
- **System** — `GET /api/health`

## Testing

- **Unit** — pytest (backend) and React Testing Library (frontend), within each project
- **E2E** — Playwright via `test/docker-compose.test.yml`, run with `LLM_MOCK=true`

## License

[MIT](LICENSE)
>>>>>>> Stashed changes
