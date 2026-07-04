'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { Portfolio, Snapshot } from './types';

/**
 * Loads portfolio + history and polls them so live price drift, snapshots, and
 * out-of-band (chat) trades are reflected without a manual refresh.
 */
export function usePortfolio(pollMs = 5000) {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([api.getPortfolio(), api.getHistory()]);
      setPortfolio(p);
      setHistory(h.snapshots ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load portfolio');
    }
  }, []);

  useEffect(() => {
    refresh();
    if (pollMs > 0) {
      timer.current = setInterval(refresh, pollMs);
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [refresh, pollMs]);

  return { portfolio, history, error, refresh };
}
