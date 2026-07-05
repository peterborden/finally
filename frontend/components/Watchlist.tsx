'use client';

/**
 * Watchlist — left-column grid: ticker, live price (flashes green/down on
 * change), daily change %, a progressive sparkline, row-selection, and
 * add/remove controls.
 *
 * Price flash (UI-02): the previous rendered price per ticker is tracked in
 * a ref; when a ticker's live price changes, `.flash-up` / `.flash-down`
 * (see `app/globals.css`) is applied to that price cell and removed again
 * after ~500ms to match the CSS transition.
 *
 * Add/remove call the `/api/watchlist` client directly (T-04-03: the raw
 * ticker string is sent as-is — the backend normalizes/validates it — and
 * rendered back only via React text nodes, never `dangerouslySetInnerHTML`)
 * then notify the parent via `onWatchlistChange` so it can re-fetch the
 * authoritative list.
 */

import { type FormEvent, useEffect, useRef, useState } from 'react';
import * as api from '../lib/api';
import type { PriceMap, WatchlistEntry } from '../lib/types';
import type { HistoryPoint } from '../lib/useLivePrices';
import Sparkline from './Sparkline';

export interface WatchlistProps {
  entries: WatchlistEntry[];
  prices: PriceMap;
  history: Record<string, HistoryPoint[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onWatchlistChange: () => void;
}

const FLASH_DURATION_MS = 500;

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatChangePercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function signColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return 'text-gray-400';
  return value > 0 ? 'text-up' : 'text-down';
}

export default function Watchlist({
  entries,
  prices,
  history,
  selected,
  onSelect,
  onWatchlistChange,
}: WatchlistProps) {
  const [flashes, setFlashes] = useState<Record<string, 'up' | 'down'>>({});
  const prevPricesRef = useRef<Record<string, number>>({});
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Detect per-ticker price changes on every SSE update and flash the cell.
  useEffect(() => {
    for (const [ticker, event] of Object.entries(prices)) {
      const prevPrice = prevPricesRef.current[ticker];
      if (prevPrice !== undefined && event.price !== prevPrice) {
        const direction: 'up' | 'down' = event.price > prevPrice ? 'up' : 'down';
        setFlashes((current) => ({ ...current, [ticker]: direction }));

        const existingTimer = timersRef.current[ticker];
        if (existingTimer) clearTimeout(existingTimer);
        timersRef.current[ticker] = setTimeout(() => {
          setFlashes((current) => {
            if (!(ticker in current)) return current;
            const next = { ...current };
            delete next[ticker];
            return next;
          });
          delete timersRef.current[ticker];
        }, FLASH_DURATION_MS);
      }
      prevPricesRef.current[ticker] = event.price;
    }
  }, [prices]);

  // Clear any pending flash timers on unmount.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const timer of Object.values(timers)) {
        clearTimeout(timer);
      }
    };
  }, []);

  const [newTicker, setNewTicker] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) return;

    setPending(true);
    setError(null);
    try {
      await api.addTicker(ticker);
      setNewTicker('');
      onWatchlistChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add ticker');
    } finally {
      setPending(false);
    }
  }

  async function handleRemove(ticker: string) {
    setError(null);
    try {
      await api.removeTicker(ticker);
      onWatchlistChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove ticker');
    }
  }

  return (
    <div className="flex h-full flex-col bg-panel">
      <form onSubmit={handleAdd} className="flex gap-2 border-b border-border-muted p-3">
        <input
          value={newTicker}
          onChange={(event) => setNewTicker(event.target.value)}
          placeholder="Add ticker..."
          aria-label="Add ticker"
          disabled={pending}
          className="min-w-0 flex-1 rounded border border-border-muted bg-base px-2 py-1 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-blue"
        />
        <button
          type="submit"
          disabled={pending || !newTicker.trim()}
          className="shrink-0 rounded bg-purple px-3 py-1 text-sm font-semibold text-gray-100 disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {error && (
        <div className="border-b border-border-muted bg-base/40 px-3 py-2 text-xs text-down">{error}</div>
      )}

      <ul className="flex-1 overflow-y-auto">
        {entries.map((entry) => {
          const ticker = entry.ticker;
          const live = prices[ticker];
          const price = live?.price ?? entry.price ?? null;
          const changePercent = live?.change_percent ?? entry.change_percent ?? null;
          const flash = flashes[ticker];
          const isSelected = selected === ticker;
          const points = history[ticker] ?? [];

          return (
            <li
              key={ticker}
              onClick={() => onSelect(ticker)}
              className={`flex cursor-pointer items-center gap-3 border-b border-l-2 border-border-muted/50 px-3 py-2 transition-colors hover:bg-base/50 ${
                isSelected ? 'border-l-accent bg-base/40' : 'border-l-transparent'
              }`}
            >
              <div className="w-16 shrink-0 font-semibold text-gray-100">{ticker}</div>
              <div
                className={`w-20 shrink-0 rounded px-1 text-right tabular text-gray-200 ${
                  flash === 'up' ? 'flash-up' : flash === 'down' ? 'flash-down' : ''
                }`}
              >
                {formatPrice(price)}
              </div>
              <div className={`w-16 shrink-0 text-right tabular text-xs ${signColorClass(changePercent)}`}>
                {formatChangePercent(changePercent)}
              </div>
              <div className="flex flex-1 justify-end">
                <Sparkline points={points} width={70} height={24} />
              </div>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  void handleRemove(ticker);
                }}
                aria-label={`Remove ${ticker}`}
                className="shrink-0 px-1 text-gray-500 hover:text-down"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
