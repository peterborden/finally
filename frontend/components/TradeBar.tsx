'use client';

import { useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { fmtMoney } from '@/lib/format';
import type { PriceMap } from '@/lib/types';

interface TradeBarProps {
  prices: PriceMap;
  selected: string | null;
  onTraded: () => void;
}

type Note = { kind: 'ok' | 'err'; text: string } | null;

export function TradeBar({ prices, selected, onTraded }: TradeBarProps) {
  const [ticker, setTicker] = useState('');
  const [qty, setQty] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<Note>(null);

  // Default the ticker field to the currently selected symbol when empty.
  const effectiveTicker = (ticker || selected || '').toUpperCase();
  const livePrice = effectiveTicker ? prices[effectiveTicker]?.price ?? null : null;
  const quantity = parseFloat(qty);
  const estCost = livePrice != null && !Number.isNaN(quantity) ? livePrice * quantity : null;

  async function submit(side: 'buy' | 'sell', e: FormEvent) {
    e.preventDefault();
    const t = effectiveTicker.trim();
    if (!t) {
      setNote({ kind: 'err', text: 'Enter a ticker.' });
      return;
    }
    if (Number.isNaN(quantity) || quantity <= 0) {
      setNote({ kind: 'err', text: 'Enter a quantity > 0.' });
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      const res = await api.trade({ ticker: t, quantity, side });
      if (res.success && res.trade) {
        setNote({
          kind: 'ok',
          text: `${side === 'buy' ? 'Bought' : 'Sold'} ${quantity} ${t} @ ${fmtMoney(res.trade.price)}`,
        });
        setQty('');
        onTraded();
      } else {
        setNote({ kind: 'err', text: res.error ?? 'Trade failed.' });
      }
    } catch (e2) {
      setNote({ kind: 'err', text: e2 instanceof Error ? e2.message : 'Trade failed.' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex shrink-0 flex-col gap-1 border-t border-border-subtle bg-bg-panel px-3 py-2">
      <form className="flex items-center gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder={selected ? selected : 'TICKER'}
          aria-label="Trade ticker"
          className="w-24 rounded border border-border-subtle bg-bg-base px-2 py-1 text-sm uppercase text-gray-100 outline-none focus:border-brand"
        />
        <input
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder="Qty"
          inputMode="decimal"
          aria-label="Trade quantity"
          className="w-20 rounded border border-border-subtle bg-bg-base px-2 py-1 text-sm tabular-nums text-gray-100 outline-none focus:border-brand"
        />
        <span className="min-w-[7rem] text-xs text-flat">
          {livePrice != null ? `@ ${fmtMoney(livePrice)}` : '@ —'}
          {estCost != null && <span className="ml-1 text-gray-300">≈ {fmtMoney(estCost)}</span>}
        </span>
        <button
          type="submit"
          onClick={(e) => submit('buy', e)}
          disabled={busy}
          className="rounded bg-submit px-4 py-1 text-sm font-semibold text-white transition-colors hover:brightness-110 disabled:opacity-50"
        >
          Buy
        </button>
        <button
          type="submit"
          onClick={(e) => submit('sell', e)}
          disabled={busy}
          className="rounded border border-down px-4 py-1 text-sm font-semibold text-down transition-colors hover:bg-down/10 disabled:opacity-50"
        >
          Sell
        </button>
      </form>
      {note && (
        <p role="status" className={`text-xs ${note.kind === 'ok' ? 'text-up' : 'text-down'}`}>
          {note.text}
        </p>
      )}
    </div>
  );
}
