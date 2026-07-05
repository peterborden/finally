/**
 * Shared TypeScript types mirroring the backend response shapes.
 *
 * Source of truth for each type is documented inline. Keep this file in
 * sync with the backend Pydantic models / dataclasses it mirrors.
 */

/** Direction of the most recent price move. */
export type Direction = 'up' | 'down' | 'flat';

/**
 * One ticker's price update, as emitted per-ticker inside the SSE payload
 * object (see backend `app/market/models.py` PriceUpdate.to_dict and
 * `app/market/stream.py`).
 *
 * `change_percent` here is already a PERCENTAGE (e.g. 0.5 means 0.5%).
 */
export interface PriceEvent {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: Direction;
}

/** The full SSE payload: an object keyed by ticker symbol. */
export type PriceMap = Record<string, PriceEvent>;

/**
 * A single watchlist row joined with its latest cached price (backend
 * `app/watchlist.py` WatchlistEntry). Price fields are optional/None until
 * a live price has streamed for that ticker.
 *
 * `change_percent` here is already a PERCENTAGE (e.g. 0.5 means 0.5%),
 * matching PriceEvent.
 */
export interface WatchlistEntry {
  ticker: string;
  price?: number | null;
  previous_price?: number | null;
  change?: number | null;
  change_percent?: number | null;
  direction?: Direction | null;
  added_at?: string | null;
}

/**
 * A single position joined with its live valuation (backend
 * `app/portfolio.py` PositionResponse).
 *
 * NOTE: `pct_change` here is a FRACTION (e.g. 0.05 means 5%) — unlike
 * `PriceEvent.change_percent` / `WatchlistEntry.change_percent`, which are
 * already percentages.
 */
export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pct_change: number;
}

/** Full portfolio snapshot (backend `app/portfolio.py` PortfolioResponse). */
export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  total_value: number;
  total_unrealized_pnl: number;
}

/** Response body for POST /api/portfolio/trade (backend TradeResponse). */
export interface TradeResponse {
  ticker: string;
  side: 'buy' | 'sell';
  filled_quantity: number;
  filled_price: number;
  portfolio: Portfolio;
}

/** A single row from portfolio_snapshots (backend SnapshotResponse). */
export interface Snapshot {
  id: string;
  total_value: number;
  recorded_at: string;
}

/**
 * The outcome of one auto-executed trade or watchlist change returned by
 * POST /api/chat (backend `app/chat.py` ActionResult).
 */
export interface ChatAction {
  type: 'trade' | 'watchlist';
  ticker: string;
  status: 'ok' | 'error';
  detail: string;
  side?: 'buy' | 'sell' | null;
  action?: 'add' | 'remove' | null;
  quantity?: number | null;
  filled_price?: number | null;
}

/** Response body for POST /api/chat (backend ChatResponseBody). */
export interface ChatResponse {
  message: string;
  actions: ChatAction[];
}

/** SSE connection lifecycle state, driven by EventSource onopen/onerror. */
export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting';
