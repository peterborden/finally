import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Header } from '@/components/Header';
import type { Portfolio } from '@/lib/types';

const portfolio: Portfolio = {
  cash_balance: 8075,
  positions_value: 3850,
  total_value: 11925,
  total_unrealized_pnl: 25,
  positions: [],
};

describe('Header', () => {
  it('shows live total value, cash, and P&L', () => {
    render(<Header portfolio={portfolio} status="connected" />);
    expect(screen.getByText('$11,925.00')).toBeInTheDocument();
    expect(screen.getByText('$8,075.00')).toBeInTheDocument();
    expect(screen.getByText(/\+\$25\.00/)).toBeInTheDocument();
  });

  it('renders the connection dot with the current status', () => {
    render(<Header portfolio={portfolio} status="reconnecting" />);
    const dot = screen.getByTestId('connection-dot');
    expect(dot).toHaveAttribute('data-status', 'reconnecting');
    expect(dot).toHaveTextContent('Reconnecting');
  });

  it('degrades to em dashes before the portfolio loads', () => {
    render(<Header portfolio={null} status="disconnected" />);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});
