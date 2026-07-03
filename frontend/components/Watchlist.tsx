'use client';

import { useState, type FormEvent } from 'react';
import { Panel } from './Panel';
import { Sparkline } from './Sparkline';
import { usePriceFlash, flashClass } from '@/lib/usePriceFlash';
import { fmtPrice, fmtPercent, directionColor } from '@/lib/format';
import type { Quote, WatchlistItem, PriceMap, SparkPoint } from '@/lib/types';

interface WatchlistProps {
  items: WatchlistItem[];
  prices: PriceMap;
  sparklines: Record<string, SparkPoint[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

/** Merge the persisted watchlist row with any live quote from the SSE stream. */
function mergeQuote(item: WatchlistItem, live: Quote | undefined): Quote {
  if (live) return live;
  return {
    ticker: item.ticker,
    price: item.price,
    previous_price: item.previous_price,
    change: item.change,
    change_percent: item.change_percent,
    direction: item.direction ?? 'flat',
  };
}

function WatchlistRow({
  quote,
  spark,
  selected,
  onSelect,
  onRemove,
}: {
  quote: Quote;
  spark: SparkPoint[];
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const flash = usePriceFlash(quote.price);
  return (
    <tr
      onClick={onSelect}
      data-testid={`watch-row-${quote.ticker}`}
      aria-selected={selected}
      className={`group cursor-pointer border-b border-border-muted transition-colors ${
        selected ? 'bg-brand/10' : 'hover:bg-bg-hover'
      }`}
    >
      <td className="py-1.5 pl-3 pr-2">
        <div className="flex items-center gap-1.5">
          {selected && <span className="h-3 w-0.5 rounded bg-brand" aria-hidden />}
          <span className="text-sm font-semibold text-gray-100">{quote.ticker}</span>
        </div>
      </td>
      <td className="px-2">
        <Sparkline data={spark} />
      </td>
      <td
        key={flash.seq}
        data-testid={`price-${quote.ticker}`}
        data-flash={flash.dir ?? ''}
        className={`px-2 text-right tabular-nums text-sm ${flashClass(flash)}`}
      >
        {fmtPrice(quote.price)}
      </td>
      <td className={`px-2 text-right tabular-nums text-xs ${directionColor(quote.direction)}`}>
        {fmtPercent(quote.change_percent)}
      </td>
      <td className="pr-2 text-right">
        <button
          type="button"
          aria-label={`Remove ${quote.ticker}`}
          title={`Remove ${quote.ticker}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="rounded px-1 text-flat opacity-0 transition-opacity hover:text-down group-hover:opacity-100"
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

export function Watchlist({ items, prices, sparklines, selected, onSelect, onAdd, onRemove }: WatchlistProps) {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (!t) return;
    setBusy(true);
    setErr(null);
    try {
      await onAdd(t);
      setInput('');
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Failed to add');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Watchlist"
      right={
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add ticker"
            aria-label="Add ticker"
            className="w-24 rounded border border-border-subtle bg-bg-base px-2 py-0.5 text-xs uppercase text-gray-100 outline-none focus:border-brand"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded border border-border-subtle bg-bg-hover px-2 py-0.5 text-xs text-brand hover:border-brand disabled:opacity-50"
          >
            +
          </button>
        </form>
      }
      bodyClassName="overflow-y-auto"
    >
      {err && <p className="px-3 py-1 text-xs text-down">{err}</p>}
      <table className="w-full border-collapse">
        <thead className="sticky top-0 bg-bg-panel text-[10px] uppercase tracking-wider text-flat">
          <tr className="border-b border-border-subtle">
            <th className="py-1 pl-3 text-left font-medium">Symbol</th>
            <th className="px-2 text-left font-medium">Trend</th>
            <th className="px-2 text-right font-medium">Price</th>
            <th className="px-2 text-right font-medium">Chg%</th>
            <th className="pr-2" />
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-xs text-flat">
                No tickers. Add one above.
              </td>
            </tr>
          )}
          {items.map((item) => {
            const quote = mergeQuote(item, prices[item.ticker]);
            return (
              <WatchlistRow
                key={item.ticker}
                quote={quote}
                spark={sparklines[item.ticker] ?? []}
                selected={selected === item.ticker}
                onSelect={() => onSelect(item.ticker)}
                onRemove={() => onRemove(item.ticker)}
              />
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
