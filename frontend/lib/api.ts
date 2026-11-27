// Same-origin REST client for the FastAPI backend (BUILD_CONTRACT §5).
import type {
  Portfolio,
  HistoryResponse,
  WatchlistResponse,
  WatchlistItem,
  TradeRequest,
  TradeResult,
  ChatResponse,
} from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* body was not JSON; keep status text */
    }
    throw new ApiError(detail, res.status);
  }
  // 204/empty guard.
  const text = await res.text();
  return (text ? JSON.parse(text) : {}) as T;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const api = {
  getPortfolio: () => request<Portfolio>('/api/portfolio'),

  getHistory: () => request<HistoryResponse>('/api/portfolio/history'),

  getWatchlist: () => request<WatchlistResponse>('/api/watchlist'),

  addWatchlist: (ticker: string) =>
    request<WatchlistItem>('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
    }),

  removeWatchlist: (ticker: string) =>
    request<{ removed: boolean }>(`/api/watchlist/${encodeURIComponent(ticker.trim().toUpperCase())}`, {
      method: 'DELETE',
    }),

  trade: (body: TradeRequest) =>
    request<TradeResult>('/api/portfolio/trade', {
      method: 'POST',
      body: JSON.stringify({
        ticker: body.ticker.trim().toUpperCase(),
        quantity: body.quantity,
        side: body.side,
      }),
    }),

  chat: (message: string) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
};
