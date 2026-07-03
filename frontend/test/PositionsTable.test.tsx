import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PositionsTable } from '@/components/PositionsTable';
import type { Portfolio } from '@/lib/types';

const portfolio: Portfolio = {
  cash_balance: 8075,
  positions_value: 3850,
  total_value: 11925,
  total_unrealized_pnl: 25,
  positions: [
    {
      ticker: 'AAPL',
      quantity: 10,
      avg_cost: 190,
      current_price: 192.5,
      market_value: 1925,
      unrealized_pnl: 25,
      unrealized_pnl_percent: 1.32,
    },
    {
      ticker: 'TSLA',
      quantity: 5,
      avg_cost: 400,
      current_price: 385,
      market_value: 1925,
      unrealized_pnl: -75,
      unrealized_pnl_percent: -3.75,
    },
  ],
};

describe('PositionsTable', () => {
  it('renders position rows with computed money/percent columns', () => {
    render(<PositionsTable portfolio={portfolio} />);
    const aapl = screen.getByTestId('pos-row-AAPL');
    expect(aapl).toHaveTextContent('AAPL');
    expect(aapl).toHaveTextContent('190.00'); // avg cost
    expect(aapl).toHaveTextContent('192.50'); // current price
    expect(aapl).toHaveTextContent('$1,925.00'); // market value
    expect(aapl).toHaveTextContent('+$25.00'); // unrealized pnl
    expect(aapl).toHaveTextContent('+1.32%');
  });

  it('color-codes a losing position red', () => {
    render(<PositionsTable portfolio={portfolio} />);
    const tsla = screen.getByTestId('pos-row-TSLA');
    expect(tsla).toHaveTextContent('-$75.00');
    const loss = tsla.querySelector('.text-down');
    expect(loss).toBeTruthy();
  });

  it('shows an empty state when there are no positions', () => {
    render(<PositionsTable portfolio={{ ...portfolio, positions: [] }} />);
    expect(screen.getByText(/No open positions/i)).toBeInTheDocument();
  });

  it('selects a ticker when a row is clicked', async () => {
    const onSelect = vi.fn();
    render(<PositionsTable portfolio={portfolio} onSelect={onSelect} />);
    await userEvent.click(screen.getByTestId('pos-row-TSLA'));
    expect(onSelect).toHaveBeenCalledWith('TSLA');
  });
});
