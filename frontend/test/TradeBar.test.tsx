import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TradeBar } from '@/components/TradeBar';
import { api } from '@/lib/api';
import type { PriceMap } from '@/lib/types';

vi.mock('@/lib/api', () => ({ api: { trade: vi.fn() } }));
const mockedTrade = vi.mocked(api.trade);

const prices: PriceMap = {
  AAPL: { ticker: 'AAPL', price: 192.5, previous_price: 191, change: 1.5, change_percent: 0.78, direction: 'up' },
};

describe('TradeBar', () => {
  beforeEach(() => mockedTrade.mockReset());

  it('shows the live price and estimated cost for the selected ticker', async () => {
    render(<TradeBar prices={prices} selected="AAPL" onTraded={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Trade quantity'), '2');
    expect(screen.getByText(/@ \$192\.50/)).toBeInTheDocument();
    expect(screen.getByText(/≈ \$385\.00/)).toBeInTheDocument();
  });

  it('executes a buy at market and reports the fill', async () => {
    mockedTrade.mockResolvedValue({
      success: true,
      error: null,
      trade: { ticker: 'AAPL', side: 'buy', quantity: 2, price: 192.5, executed_at: 'x' },
      position: { ticker: 'AAPL', quantity: 2, avg_cost: 192.5 },
      cash_balance: 9615,
    });
    const onTraded = vi.fn();
    render(<TradeBar prices={prices} selected="AAPL" onTraded={onTraded} />);
    await userEvent.type(screen.getByLabelText('Trade quantity'), '2');
    await userEvent.click(screen.getByRole('button', { name: 'Buy' }));

    await waitFor(() => expect(mockedTrade).toHaveBeenCalledWith({ ticker: 'AAPL', quantity: 2, side: 'buy' }));
    expect(onTraded).toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent(/Bought 2 AAPL/i);
  });

  it('surfaces a validation error from the backend', async () => {
    mockedTrade.mockResolvedValue({
      success: false,
      error: 'Insufficient cash: need $1925.00, have $100.00',
      trade: null,
      position: null,
      cash_balance: 100,
    });
    render(<TradeBar prices={prices} selected="AAPL" onTraded={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Trade quantity'), '10');
    await userEvent.click(screen.getByRole('button', { name: 'Buy' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/Insufficient cash/i));
  });

  it('blocks submission without a quantity', async () => {
    render(<TradeBar prices={prices} selected="AAPL" onTraded={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Buy' }));
    expect(mockedTrade).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent(/quantity/i);
  });
});
