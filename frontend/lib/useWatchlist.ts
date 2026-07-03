'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import type { WatchlistItem } from './types';

/**
 * Owns the persisted watchlist (order + membership) from GET /api/watchlist.
 * Live prices are layered on top from the SSE stream by the consumer, so this
 * hook only needs to reload when membership changes (add/remove, chat actions).
 */
export function useWatchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.getWatchlist();
      setItems(res.watchlist ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  }, []);

  const add = useCallback(
    async (ticker: string) => {
      await api.addWatchlist(ticker);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (ticker: string) => {
      await api.removeWatchlist(ticker);
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { items, error, loading, refresh, add, remove };
}
