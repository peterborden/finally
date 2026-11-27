import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel } from '@/components/ChatPanel';
import { api } from '@/lib/api';
import type { ChatResponse } from '@/lib/types';

vi.mock('@/lib/api', () => ({ api: { chat: vi.fn() } }));
const mockedChat = vi.mocked(api.chat);

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe('ChatPanel', () => {
  beforeEach(() => mockedChat.mockReset());

  it('renders the welcome message and input', () => {
    render(<ChatPanel collapsed={false} onToggle={vi.fn()} onActions={vi.fn()} />);
    expect(screen.getByText(/I'm FinAlly/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Message FinAlly')).toBeInTheDocument();
  });

  it('shows the user message and a loading indicator while awaiting the reply', async () => {
    const d = deferred<ChatResponse>();
    mockedChat.mockReturnValue(d.promise);

    render(<ChatPanel collapsed={false} onToggle={vi.fn()} onActions={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Message FinAlly'), 'buy 5 AAPL');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    // User bubble appears immediately; loading dots visible.
    expect(screen.getByText('buy 5 AAPL')).toBeInTheDocument();
    expect(screen.getByTestId('chat-loading')).toBeInTheDocument();

    d.resolve({
      message: 'Bought 5 shares of AAPL at $192.50.',
      trades: [{ ticker: 'AAPL', side: 'buy', quantity: 5, price: 192.5, executed_at: '2026-07-03T00:00:00Z' }],
      watchlist_changes: [],
      errors: [],
    });

    await waitFor(() => expect(screen.queryByTestId('chat-loading')).not.toBeInTheDocument());
    expect(screen.getByText(/Bought 5 shares of AAPL/i)).toBeInTheDocument();
    // Inline trade confirmation chip.
    expect(screen.getByTestId('chat-action')).toHaveTextContent('BUY 5 AAPL');
  });

  it('fires onActions when the response executed a trade', async () => {
    const onActions = vi.fn();
    mockedChat.mockResolvedValue({
      message: 'Done.',
      trades: [{ ticker: 'AAPL', side: 'buy', quantity: 1, price: 100, executed_at: 'x' }],
      watchlist_changes: [],
      errors: [],
    });
    render(<ChatPanel collapsed={false} onToggle={vi.fn()} onActions={onActions} />);
    await userEvent.type(screen.getByLabelText('Message FinAlly'), 'buy 1 AAPL');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(onActions).toHaveBeenCalled());
  });

  it('surfaces an error bubble when the request fails', async () => {
    // Lazily created single-use rejection: the promise is created only when the
    // component calls api.chat and is awaited (and caught) in the same tick, so it
    // is never observed as an unhandled rejection by the runner.
    mockedChat.mockImplementationOnce(() => Promise.reject(new Error('boom')));
    render(<ChatPanel collapsed={false} onToggle={vi.fn()} onActions={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Message FinAlly'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText(/couldn't reach the assistant/i)).toBeInTheDocument();
  });

  it('collapses to a rail when collapsed', () => {
    render(<ChatPanel collapsed onToggle={vi.fn()} onActions={vi.fn()} />);
    expect(screen.queryByTestId('chat-panel')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Open AI assistant')).toBeInTheDocument();
  });
});
