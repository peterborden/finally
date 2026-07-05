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

## Quick Start

```bash
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

## Run with Docker

1. Copy the environment template and fill in your keys (or leave them blank / set `LLM_MOCK=true` to run without any keys):

   ```bash
   cp .env.example .env
   ```

2. Launch with one command:

   - **macOS/Linux**: `scripts/start_mac.sh`
   - **Windows**: `scripts/start_windows.ps1`

   Both scripts build the `finally` image only if it doesn't already exist (pass `--build` / `-Build` to force a rebuild), start the container with the `finally-data` volume mounted, and print the app URL. Re-running either script is safe — it will not create a duplicate container.

3. Equivalent raw Docker commands, if you prefer not to use the scripts:

   ```bash
   docker build -t finally .
   docker run -d --name finally -v finally-data:/app/db -p 8000:8000 --env-file .env finally
   ```

   Or with Docker Compose:

   ```bash
   docker compose up
   ```

4. Open **http://localhost:8000**.

5. To stop: `scripts/stop_mac.sh` (macOS/Linux) or `scripts/stop_windows.ps1` (Windows). Stopping removes the container but preserves the `finally-data` volume, so your portfolio, watchlist, and trade history persist across restarts.

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
