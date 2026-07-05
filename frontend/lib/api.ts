/**
 * Thin fetch wrappers for the backend `/api/*` REST endpoints.
 *
 * All requests use relative paths — the frontend is served same-origin by
 * FastAPI, so no CORS configuration is needed or used here.
 *
 * On a non-ok response, each helper reads the FastAPI HTTPException JSON
 * shape (`{"detail": "..."}`) and throws an Error carrying that detail so
 * callers can surface e.g. "insufficient cash" inline (T-04-01: never leak
 * anything beyond the backend's own detail string).
 */

import type {
  ChatResponse,
  Portfolio,
  Snapshot,
  TradeResponse,
  WatchlistEntry,
} from './types';

async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body?.detail === 'string') {
      return body.detail;
    }
  } catch {
    // Response body wasn't JSON (or was empty) — fall through to status text.
  }
  return `${res.status} ${res.statusText}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(await extractErrorDetail(res));
  }

  return (await res.json()) as T;
}

export function getWatchlist(): Promise<WatchlistEntry[]> {
  return request<WatchlistEntry[]>('/api/watchlist');
}

export function addTicker(ticker: string): Promise<WatchlistEntry> {
  return request<WatchlistEntry>('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify({ ticker }),
  });
}

export function removeTicker(ticker: string): Promise<{ ticker: string; removed: boolean }> {
  return request<{ ticker: string; removed: boolean }>(
    `/api/watchlist/${encodeURIComponent(ticker)}`,
    { method: 'DELETE' },
  );
}

export function getPortfolio(): Promise<Portfolio> {
  return request<Portfolio>('/api/portfolio');
}

export interface TradeParams {
  ticker: string;
  side: 'buy' | 'sell';
  quantity: number;
}

export function trade(params: TradeParams): Promise<TradeResponse> {
  return request<TradeResponse>('/api/portfolio/trade', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export function getHistory(): Promise<Snapshot[]> {
  return request<Snapshot[]>('/api/portfolio/history');
}

export function sendChat(message: string): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
