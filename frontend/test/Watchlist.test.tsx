import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Watchlist } from '@/components/Watchlist';
import type { WatchlistItem, PriceMap } from '@/lib/types';

const items: WatchlistItem[] = [
  { ticker: 'AAPL', price: 192.5, previous_price: 191, change: 1.5, change_percent: 0.78, direction: 'up' },
  { ticker: 'GOOGL', price: 175, previous_price: 176, change: -1, change_percent: -0.57, direction: 'down' },
];

function setup(overrides: Partial<Parameters<typeof Watchlist>[0]> = {}) {
  const onSelect = vi.fn();
  const onAdd = vi.fn().mockResolvedValue(undefined);
  const onRemove = vi.fn().mockResolvedValue(undefined);
  const props = {
    items,
    prices: {} as PriceMap,
    sparklines: {},
    selected: 'AAPL',
    onSelect,
    onAdd,
    onRemove,
    ...overrides,
  };
  const utils = render(<Watchlist {...props} />);
  return { onSelect, onAdd, onRemove, ...utils };
}

describe('Watchlist', () => {
  it('renders each ticker with its price and change', () => {
    setup();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
    expect(screen.getByTestId('price-AAPL')).toHaveTextContent('192.50');
    expect(screen.getByText('+0.78%')).toBeInTheDocument();
    expect(screen.getByText('-0.57%')).toBeInTheDocument();
  });

  it('shows an em dash when a price is null (no tick yet)', () => {
    setup({
      items: [{ ticker: 'PYPL', price: null, previous_price: null, change: null, change_percent: null, direction: 'flat' }],
      selected: null,
    });
    expect(screen.getByTestId('price-PYPL')).toHaveTextContent('—');
  });

  it('selects a ticker when its row is clicked', async () => {
    const { onSelect } = setup();
    await userEvent.click(screen.getByText('GOOGL'));
    expect(onSelect).toHaveBeenCalledWith('GOOGL');
  });

  it('adds a ticker through the form', async () => {
    const { onAdd } = setup();
    await userEvent.type(screen.getByLabelText('Add ticker'), 'nvda');
    await userEvent.click(screen.getByRole('button', { name: '+' }));
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith('NVDA'));
  });

  it('removes a ticker via the row remove button', async () => {
    const { onRemove } = setup();
    await userEvent.click(screen.getByLabelText('Remove GOOGL'));
    expect(onRemove).toHaveBeenCalledWith('GOOGL');
  });

  it('flashes green when the live price ticks up', () => {
    const base: PriceMap = {
      AAPL: { ticker: 'AAPL', price: 192.5, previous_price: 191, change: 1.5, change_percent: 0.78, direction: 'up' },
    };
    const { rerender } = render(
      <Watchlist
        items={[items[0]]}
        prices={base}
        sparklines={{}}
        selected="AAPL"
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    // No flash on first render.
    expect(screen.getByTestId('price-AAPL')).not.toHaveClass('animate-flash-up');

    const up: PriceMap = { AAPL: { ...base.AAPL, price: 193.75, direction: 'up' } };
    rerender(
      <Watchlist
        items={[items[0]]}
        prices={up}
        sparklines={{}}
        selected="AAPL"
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    const cell = screen.getByTestId('price-AAPL');
    expect(cell).toHaveClass('animate-flash-up');
    expect(cell).toHaveAttribute('data-flash', 'up');
  });

  it('flashes red when the live price ticks down', () => {
    const base: PriceMap = {
      AAPL: { ticker: 'AAPL', price: 192.5, previous_price: 191, change: 1.5, change_percent: 0.78, direction: 'up' },
    };
    const { rerender } = render(
      <Watchlist items={[items[0]]} prices={base} sparklines={{}} selected="AAPL" onSelect={vi.fn()} onAdd={vi.fn()} onRemove={vi.fn()} />,
    );
    const down: PriceMap = { AAPL: { ...base.AAPL, price: 190.0, direction: 'down' } };
    rerender(
      <Watchlist items={[items[0]]} prices={down} sparklines={{}} selected="AAPL" onSelect={vi.fn()} onAdd={vi.fn()} onRemove={vi.fn()} />,
    );
    expect(screen.getByTestId('price-AAPL')).toHaveClass('animate-flash-down');
  });

  it('prefers the live SSE quote over the persisted row', () => {
    const prices: PriceMap = {
      AAPL: { ticker: 'AAPL', price: 200.0, previous_price: 199, change: 1, change_percent: 0.5, direction: 'up' },
    };
    setup({ prices });
    expect(screen.getByTestId('price-AAPL')).toHaveTextContent('200.00');
  });

  it('renders an empty state with no tickers', () => {
    setup({ items: [] });
    expect(screen.getByText(/No tickers/i)).toBeInTheDocument();
  });
});
