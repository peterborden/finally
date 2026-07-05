'use client';

/**
 * PositionsTable — ticker, quantity, avg cost, current price, unrealized
 * P&L, and % change for every held position.
 *
 * `position.pct_change` from the backend is a FRACTION (e.g. 0.05 means
 * 5%) — see `frontend/lib/types.ts` Position doc comment — so it's
 * multiplied by 100 before rendering with a "%" suffix. When a live price
 * is available in `prices`, current price / unrealized P&L / % change are
 * recomputed from it so the table tracks the SSE stream between portfolio
 * re-fetches; otherwise the last-fetched `position` values are shown as-is.
 */

import type { Position, PriceMap } from '../lib/types';

export interface PositionsTableProps {
  positions: Position[];
  prices: PriceMap;
}

interface DisplayRow {
  ticker: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  unrealizedPnl: number;
  pctChange: number;
}

function toDisplayRow(position: Position, prices: PriceMap): DisplayRow {
  const livePrice = prices[position.ticker]?.price;

  if (livePrice === undefined) {
    return {
      ticker: position.ticker,
      quantity: position.quantity,
      avgCost: position.avg_cost,
      currentPrice: position.current_price,
      unrealizedPnl: position.unrealized_pnl,
      pctChange: position.pct_change,
    };
  }

  const unrealizedPnl = (livePrice - position.avg_cost) * position.quantity;
  const pctChange = position.avg_cost !== 0 ? livePrice / position.avg_cost - 1 : 0;

  return {
    ticker: position.ticker,
    quantity: position.quantity,
    avgCost: position.avg_cost,
    currentPrice: livePrice,
    unrealizedPnl,
    pctChange,
  };
}

function formatCurrency(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function signColorClass(value: number): string {
  return value >= 0 ? 'text-up' : 'text-down';
}

export default function PositionsTable({ positions, prices }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <div className="p-4 text-sm text-gray-500">No open positions.</div>
    );
  }

  const rows = positions.map((position) => toDisplayRow(position, prices));

  return (
    <table className="w-full text-sm tabular">
      <thead>
        <tr className="border-b border-border-muted text-left text-xs text-gray-400">
          <th className="px-3 py-2 font-normal">Ticker</th>
          <th className="px-3 py-2 font-normal text-right">Quantity</th>
          <th className="px-3 py-2 font-normal text-right">Avg Cost</th>
          <th className="px-3 py-2 font-normal text-right">Current Price</th>
          <th className="px-3 py-2 font-normal text-right">Unrealized P&amp;L</th>
          <th className="px-3 py-2 font-normal text-right">% Change</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.ticker} className="border-b border-border-muted/50">
            <td className="px-3 py-2 font-semibold text-gray-100">{row.ticker}</td>
            <td className="px-3 py-2 text-right text-gray-200">{row.quantity}</td>
            <td className="px-3 py-2 text-right text-gray-200">{formatCurrency(row.avgCost)}</td>
            <td className="px-3 py-2 text-right text-gray-200">{formatCurrency(row.currentPrice)}</td>
            <td className={`px-3 py-2 text-right ${signColorClass(row.unrealizedPnl)}`}>
              {formatCurrency(row.unrealizedPnl)}
            </td>
            <td className={`px-3 py-2 text-right ${signColorClass(row.pctChange)}`}>
              {(row.pctChange * 100).toFixed(2)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
