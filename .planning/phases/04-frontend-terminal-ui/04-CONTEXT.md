# Phase 4: Frontend Terminal UI - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped); design contract locked inline below.

<domain>
## Phase Boundary

A dark, data-dense Bloomberg-style Next.js single-page terminal (static export) that streams live prices over SSE and drives all watchlist, trading, and AI-chat interactions against the existing backend API. Requirements: UI-01..UI-10.

</domain>

<canonical_refs>
## Canonical References

- `planning/PLAN.md` §2 (UX + Visual Design + Color Scheme), §10 (Frontend Design — layout, components, technical notes), §3/§11 (static export served by FastAPI). AUTHORITATIVE.
- Backend API already built (phases 1-3): `GET /api/stream/prices` (SSE), `GET/POST/DELETE /api/watchlist`, `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`, `POST /api/chat`, `GET /api/health`. Same-origin `/api/*` — no CORS.
- SSE event shape (from backend `app/market/stream.py`): each event carries ticker, price, previous_price, timestamp, change direction (confirm exact JSON by reading `app/market/models.py` PriceUpdate.to_dict and `app/market/stream.py`).
</canonical_refs>

<decisions>
## Implementation Decisions — LOCKED DESIGN CONTRACT

### Stack
- **Next.js (app router) + TypeScript, static export** (`next.config.js` → `output: 'export'`, `images.unoptimized: true`). Builds to `frontend/out`.
- **Tailwind CSS** with a custom dark theme. **No external network at runtime** — all same-origin.
- **Charts:** `lightweight-charts` (TradingView, canvas — for the main price chart and the P&L line chart) and `recharts` (for the portfolio treemap/heatmap). Sparklines: lightweight inline SVG (hand-rolled, no dep) accumulated from SSE since page load.
- All API calls to relative `/api/*`. SSE via native `EventSource('/api/stream/prices')` with EventSource's built-in auto-reconnect.

### Color & Theme (exact, from PLAN.md §2)
- Backgrounds: base `#0d1117`, panels `#1a1a2e`, muted gray borders (e.g. `#2a2a3a`), never pure black.
- Accent yellow `#ecad0a`; blue primary `#209dd7`; purple secondary `#753991` (submit/buy-confirm buttons).
- Uptick green (e.g. `#26a269`/`#3fb950`), downtick red (e.g. `#f85149`). Price flash: brief bg highlight fading over ~500ms via CSS transition.
- Monospace/tabular numerals for prices; dense spacing; desktop-first, functional on tablet.

### Layout (Bloomberg-style, single page)
- **Header (top bar):** app name, live total portfolio value, cash balance, connection status dot (green=connected / yellow=reconnecting / red=disconnected).
- **Left column — Watchlist grid:** ticker, current price (flashes green/red on change), daily change %, progressive sparkline (accumulated from SSE). Clicking a row selects that ticker. Add-ticker input; remove (×) per row.
- **Center — Main chart area:** larger price-over-time chart for the selected ticker (lightweight-charts), built from accumulated SSE ticks since load.
- **Right — AI chat panel (collapsible sidebar):** scrolling message history, input, loading indicator while awaiting `/api/chat`, inline confirmations of executed trades/watchlist changes returned in the response.
- **Bottom band:** portfolio heatmap/treemap (recharts Treemap — rectangle per position, sized by weight, colored by P&L green↔red), P&L line chart (from `/api/portfolio/history`), positions table (ticker, qty, avg cost, current price, unrealized P&L, % change), and a trade bar (ticker field, quantity field, Buy + Sell buttons — instant market order, no confirmation dialog).

### Data & State
- On load: fetch `/api/watchlist`, `/api/portfolio`, `/api/portfolio/history`; open the SSE stream.
- Maintain an in-memory per-ticker price history (array of {t, price}) accumulated from SSE for sparklines + the main chart; cap length to keep memory bounded.
- After any trade (manual trade bar or via chat) or watchlist change: re-fetch `/api/portfolio` (and `/api/watchlist`) so positions/cash/total update instantly. Total value in the header updates live from cache prices × positions.
- Trade bar & chat POST to the backend; show returned errors (e.g. insufficient cash) inline.
- Connection dot driven by EventSource `onopen`/`onerror` state.

### Build/Serve integration
- Output `frontend/out` is what FastAPI serves via `FRONTEND_DIST` (Phase 1 made it configurable). This phase must make `npm run build` produce the export; Phase 5 wires the Dockerfile to build it and point FRONTEND_DIST at it. For local verification, build and set FRONTEND_DIST to frontend/out, then confirm the app loads at `/`.

</decisions>

<code_context>
## Existing Code Insights

`frontend/` is currently empty — scaffold a fresh Next.js TS project there. Backend serves whatever `FRONTEND_DIST` points at (default backend/app/static placeholder). Read `backend/app/market/models.py` + `stream.py` for the exact SSE JSON so the client parses it correctly. Read `app/portfolio.py` + `app/chat.py` response shapes so the UI consumes them correctly.

</code_context>

<specifics>
## Specific Ideas

- Use the `frontend-design` skill's guidance for a distinctive, intentional terminal aesthetic (not a templated default) — but stay within the locked color scheme.
- Keep components modular: Header, Watchlist, PriceChart, PnLChart, PortfolioHeatmap, PositionsTable, TradeBar, ChatPanel, ConnectionDot, plus an SSE hook (useLivePrices) and API client helpers.
- Price flash: add a CSS class on change, remove after the transition.
- Sparklines fill in progressively — empty until enough SSE ticks accumulate.

</specifics>

<deferred>
## Deferred Ideas

Server-side historical price data is Out of Scope — charts build from SSE-accumulated data since page load (per PLAN.md). Mobile-first layout is out — desktop-first, tablet-functional.

</deferred>
