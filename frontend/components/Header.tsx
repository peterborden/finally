'use client';

/**
 * Header — top bar: wordmark, live total portfolio value, cash balance, and
 * the SSE connection-status dot.
 *
 * Total value is recomputed here (not just read from the fetched
 * `portfolio` snapshot) so it ticks with every SSE price update: cash +
 * sum(quantity * live price), falling back to `position.current_price`
 * then `position.avg_cost` when a ticker hasn't streamed yet.
 */

import type { ConnectionStatus, Portfolio, PriceMap } from '../lib/types';
import ConnectionDot from './ConnectionDot';

export interface HeaderProps {
  portfolio: Portfolio | null;
  prices: PriceMap;
  status: ConnectionStatus;
}

function formatCurrency(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function computeLiveTotalValue(portfolio: Portfolio, prices: PriceMap): number {
  const positionsValue = portfolio.positions.reduce((sum, position) => {
    const livePrice = prices[position.ticker]?.price;
    const price = livePrice ?? position.current_price ?? position.avg_cost;
    return sum + position.quantity * price;
  }, 0);
  return portfolio.cash_balance + positionsValue;
}

export default function Header({ portfolio, prices, status }: HeaderProps) {
  const totalValue = portfolio ? computeLiveTotalValue(portfolio, prices) : null;
  const cashBalance = portfolio?.cash_balance ?? null;

  return (
    <header className="flex items-center justify-between border-b border-border-muted bg-panel px-4 py-3">
      <h1 className="text-lg font-semibold text-accent">FinAlly</h1>
      <div className="flex items-center gap-6">
        <div className="text-right tabular">
          <div className="text-xs text-gray-400">Total Value</div>
          <div className="text-base font-semibold text-gray-100">
            {totalValue === null ? '—' : formatCurrency(totalValue)}
          </div>
        </div>
        <div className="text-right tabular">
          <div className="text-xs text-gray-400">Cash</div>
          <div className="text-base font-semibold text-gray-100">
            {cashBalance === null ? '—' : formatCurrency(cashBalance)}
          </div>
        </div>
        <ConnectionDot status={status} />
      </div>
    </header>
  );
}
