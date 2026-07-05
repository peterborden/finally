'use client';

/**
 * useLivePrices — subscribes to the backend SSE price stream and exposes a
 * live price map, per-ticker history, and the connection status.
 *
 * The SSE payload (see backend `app/market/stream.py`) is a single JSON
 * OBJECT per event, keyed by ticker symbol:
 *
 *   data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, "GOOGL": {...}}
 *
 * NOT one ticker per event. `EventSource` retries automatically on error
 * (the backend also sends a `retry: 1000` directive) — this hook never
 * manually closes and reopens the connection on error; it just reflects
 * the reconnecting state until `onopen` fires again.
 */

import { useEffect, useRef, useState } from 'react';
import type { ConnectionStatus, PriceEvent, PriceMap } from './types';

/** One accumulated price point for a ticker's history / sparkline. */
export interface HistoryPoint {
  t: number;
  price: number;
}

/** The full state maintained by useLivePrices. */
export interface LivePricesState {
  prices: PriceMap;
  history: Record<string, HistoryPoint[]>;
}

const DEFAULT_HISTORY_CAP = 300;
const STREAM_URL = '/api/stream/prices';

/**
 * Pure merge step: fold one SSE payload (an object keyed by ticker) into
 * the current state, appending one history point per ticker present in the
 * payload and capping each ticker's history at `cap` points (oldest
 * dropped first). Exported standalone so it is unit-testable without a
 * DOM/EventSource.
 */
export function applyPriceEvent(
  state: LivePricesState,
  payload: Record<string, PriceEvent>,
  cap: number = DEFAULT_HISTORY_CAP,
): LivePricesState {
  const nextPrices: PriceMap = { ...state.prices };
  const nextHistory: Record<string, HistoryPoint[]> = { ...state.history };

  for (const [ticker, event] of Object.entries(payload)) {
    nextPrices[ticker] = event;

    const existing = nextHistory[ticker] ?? [];
    const appended = [...existing, { t: event.timestamp, price: event.price }];
    nextHistory[ticker] = appended.length > cap ? appended.slice(appended.length - cap) : appended;
  }

  return { prices: nextPrices, history: nextHistory };
}

export interface UseLivePricesResult extends LivePricesState {
  status: ConnectionStatus;
}

export function useLivePrices(historyCap: number = DEFAULT_HISTORY_CAP): UseLivePricesResult {
  const [state, setState] = useState<LivePricesState>({ prices: {}, history: {} });
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const capRef = useRef(historyCap);
  capRef.current = historyCap;

  useEffect(() => {
    const source = new EventSource(STREAM_URL);

    source.onopen = () => setStatus('connected');
    source.onerror = () => setStatus('reconnecting');
    source.onmessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, PriceEvent>;
        setState((prev) => applyPriceEvent(prev, payload, capRef.current));
      } catch {
        // Malformed payload — skip this event rather than crash the stream.
      }
    };

    return () => {
      source.close();
    };
  }, []);

  return { ...state, status };
}
