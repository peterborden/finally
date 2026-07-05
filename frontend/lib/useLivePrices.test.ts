import { describe, expect, it } from 'vitest';
import { applyPriceEvent, type LivePricesState } from './useLivePrices';
import type { PriceEvent } from './types';

function makeEvent(overrides: Partial<PriceEvent> = {}): PriceEvent {
  return {
    ticker: 'AAPL',
    price: 190.5,
    previous_price: 189.0,
    timestamp: 1000,
    change: 1.5,
    change_percent: 0.79,
    direction: 'up',
    ...overrides,
  };
}

const emptyState: LivePricesState = { prices: {}, history: {} };

describe('applyPriceEvent', () => {
  it('merges a single ticker into an empty state', () => {
    const payload = { AAPL: makeEvent() };
    const next = applyPriceEvent(emptyState, payload, 300);

    expect(next.prices.AAPL).toEqual(payload.AAPL);
    expect(next.history.AAPL).toEqual([{ t: 1000, price: 190.5 }]);
  });

  it('merges multiple tickers in a single payload without clobbering each other', () => {
    const payload = {
      AAPL: makeEvent({ ticker: 'AAPL', price: 190.5, timestamp: 1000 }),
      GOOGL: makeEvent({ ticker: 'GOOGL', price: 175.25, timestamp: 1000 }),
    };
    const next = applyPriceEvent(emptyState, payload, 300);

    expect(Object.keys(next.prices).sort()).toEqual(['AAPL', 'GOOGL']);
    expect(next.prices.AAPL.price).toBe(190.5);
    expect(next.prices.GOOGL.price).toBe(175.25);
    expect(next.history.AAPL).toEqual([{ t: 1000, price: 190.5 }]);
    expect(next.history.GOOGL).toEqual([{ t: 1000, price: 175.25 }]);
  });

  it('appends to existing history across successive events for the same ticker', () => {
    const first = applyPriceEvent(
      emptyState,
      { AAPL: makeEvent({ price: 190.5, timestamp: 1000 }) },
      300,
    );
    const second = applyPriceEvent(
      first,
      { AAPL: makeEvent({ price: 191.0, timestamp: 1500 }) },
      300,
    );

    expect(second.history.AAPL).toEqual([
      { t: 1000, price: 190.5 },
      { t: 1500, price: 191.0 },
    ]);
    expect(second.prices.AAPL.price).toBe(191.0);
  });

  it('does not mutate ticker histories untouched by the current payload', () => {
    const first = applyPriceEvent(
      emptyState,
      { AAPL: makeEvent({ ticker: 'AAPL', price: 190.5, timestamp: 1000 }) },
      300,
    );
    const second = applyPriceEvent(
      first,
      { GOOGL: makeEvent({ ticker: 'GOOGL', price: 175.25, timestamp: 1500 }) },
      300,
    );

    expect(second.history.AAPL).toEqual([{ t: 1000, price: 190.5 }]);
    expect(second.prices.AAPL).toEqual(first.prices.AAPL);
  });

  it('caps per-ticker history length, dropping the oldest points', () => {
    let state = emptyState;
    for (let i = 0; i < 5; i += 1) {
      state = applyPriceEvent(
        state,
        { AAPL: makeEvent({ price: 100 + i, timestamp: i }) },
        3,
      );
    }

    expect(state.history.AAPL).toEqual([
      { t: 2, price: 102 },
      { t: 3, price: 103 },
      { t: 4, price: 104 },
    ]);
  });
});
