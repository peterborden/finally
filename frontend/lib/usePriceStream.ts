'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { PriceMap, Quote, ConnectionStatus, SparkPoint } from './types';

const MAX_SPARK_POINTS = 120; // ~1 min of history at 500ms cadence.

export interface PriceStreamState {
  /** Latest quote per ticker, keyed uppercase. */
  prices: PriceMap;
  /** Accumulated price samples per ticker since page load (for sparklines). */
  sparklines: Record<string, SparkPoint[]>;
  status: ConnectionStatus;
}

/**
 * Subscribes to GET /api/stream/prices via native EventSource.
 *
 * The event payload is a JSON object keyed by ticker (§5.9). EventSource retries
 * automatically; we surface that as a `reconnecting` status and flip to
 * `connected` on the next successful message/open.
 */
export function usePriceStream(url = '/api/stream/prices'): PriceStreamState {
  const [prices, setPrices] = useState<PriceMap>({});
  const [sparklines, setSparklines] = useState<Record<string, SparkPoint[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const esRef = useRef<EventSource | null>(null);

  const ingest = useCallback((map: PriceMap) => {
    const now = Date.now();
    setPrices((prev) => ({ ...prev, ...map }));
    setSparklines((prev) => {
      const next = { ...prev };
      for (const ticker of Object.keys(map)) {
        const q: Quote = map[ticker];
        if (q.price == null || Number.isNaN(q.price)) continue;
        const series = next[ticker] ? next[ticker].slice() : [];
        series.push({ t: q.timestamp ?? now, price: q.price });
        if (series.length > MAX_SPARK_POINTS) series.splice(0, series.length - MAX_SPARK_POINTS);
        next[ticker] = series;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
      return;
    }
    setStatus('reconnecting');
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setStatus('connected');

    es.onmessage = (evt: MessageEvent) => {
      setStatus('connected');
      try {
        const data = JSON.parse(evt.data) as PriceMap;
        if (data && typeof data === 'object') ingest(data);
      } catch {
        /* ignore malformed frame */
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects unless it was explicitly closed.
      setStatus(es.readyState === EventSource.CLOSED ? 'disconnected' : 'reconnecting');
    };

    return () => {
      es.close();
      esRef.current = null;
      setStatus('disconnected');
    };
  }, [url, ingest]);

  return { prices, sparklines, status };
}
