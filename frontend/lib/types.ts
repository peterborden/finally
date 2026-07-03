// Shared types mirroring BUILD_CONTRACT §5 (HTTP) and §5.9 (SSE).

export type Direction = 'up' | 'down' | 'flat';

/** One ticker's live quote as pushed over SSE (§5.9) and returned by GET /api/watchlist (§5.4). */
export interface Quote {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: Direction;
  // Present on the SSE payload; absent from the watchlist REST shape.
  timestamp?: number;
}

/** SSE event: a JSON object keyed by ticker (§5.9). */
export type PriceMap = Record<string, Quote>;

/** GET /api/watchlist (§5.4) — items may have null price fields until first tick. */
export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: Direction;
}

export interface WatchlistResponse {
  watchlist: WatchlistItem[];
}

/** GET /api/portfolio (§5.1). */
export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  positions_value: number;
  total_value: number;
  total_unrealized_pnl: number;
  positions: Position[];
}

/** POST /api/portfolio/trade (§5.2). */
export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: 'buy' | 'sell';
}

export interface TradeResult {
  success: boolean;
  error: string | null;
  trade: {
    ticker: string;
    side: 'buy' | 'sell';
    quantity: number;
    price: number;
    executed_at: string;
  } | null;
  position: { ticker: string; quantity: number; avg_cost: number } | null;
  cash_balance: number;
}

/** GET /api/portfolio/history (§5.3). */
export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface HistoryResponse {
  snapshots: Snapshot[];
}

/** POST /api/chat (§5.7). */
export interface ChatTrade {
  ticker: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  executed_at: string;
}

export interface ChatWatchlistChange {
  ticker: string;
  action: 'add' | 'remove';
}

export interface ChatResponse {
  message: string;
  trades: ChatTrade[];
  watchlist_changes: ChatWatchlistChange[];
  errors: string[];
}

/** A rendered chat bubble in the panel. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  trades?: ChatTrade[];
  watchlist_changes?: ChatWatchlistChange[];
  errors?: string[];
  pending?: boolean;
}

/** SSE connection health for the header dot. */
export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

/** A single accumulated sparkline sample (price at a moment since page load). */
export interface SparkPoint {
  t: number;
  price: number;
}
