'use client';

/**
 * TradeBar — instant market order entry: ticker, quantity, Buy/Sell.
 *
 * Deliberately NO confirmation dialog/modal before firing the order (see
 * PLAN.md §10 and threat T-04-06: accepted risk, simulated money). On
 * success the quantity field clears and a brief inline fill note is shown;
 * on failure the backend's `detail` string (thrown as `Error.message` by
 * `lib/api.ts`) is shown inline and inputs are left as-is so the user can
 * retry. Buttons disable while a request is in flight to prevent
 * double-submission.
 */

import { useState } from 'react';
import * as api from '../lib/api';

export interface TradeBarProps {
  onTraded: () => void;
}

type Side = 'buy' | 'sell';

export default function TradeBar({ onTraded }: TradeBarProps) {
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const parsedQuantity = Number(quantity);
  const canSubmit =
    !submitting && ticker.trim().length > 0 && quantity.trim().length > 0 && parsedQuantity > 0;

  async function fire(side: Side) {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await api.trade({
        ticker: ticker.trim().toUpperCase(),
        side,
        quantity: parsedQuantity,
      });
      setQuantity('');
      setSuccess(
        `${side === 'buy' ? 'Bought' : 'Sold'} ${result.filled_quantity} ${result.ticker} @ $${result.filled_price.toFixed(2)}`,
      );
      onTraded();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      className="flex flex-wrap items-end gap-3 p-3"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs text-gray-400">
        Ticker
        <input
          className="w-24 rounded border border-border-muted bg-base px-2 py-1 text-sm uppercase text-gray-100 tabular"
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          placeholder="AAPL"
          maxLength={10}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-gray-400">
        Quantity
        <input
          className="w-24 rounded border border-border-muted bg-base px-2 py-1 text-sm text-gray-100 tabular"
          type="number"
          min="0"
          step="any"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          placeholder="10"
        />
      </label>
      <button
        type="button"
        className="rounded bg-purple px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        disabled={!canSubmit}
        onClick={() => fire('buy')}
      >
        Buy
      </button>
      <button
        type="button"
        className="rounded border border-down px-4 py-1.5 text-sm font-semibold text-down disabled:opacity-50"
        disabled={!canSubmit}
        onClick={() => fire('sell')}
      >
        Sell
      </button>
      {error && <span className="text-sm text-down">{error}</span>}
      {success && <span className="text-sm text-up">{success}</span>}
    </form>
  );
}
