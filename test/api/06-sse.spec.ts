import { test, expect } from '@playwright/test';
import { collectSseEvents } from '../support/sse';

/** §5.9 GET /api/stream/prices — event data is a JSON object keyed by ticker. */

test.describe('@api SSE price stream', () => {
  test('streams price events in the §5.9 shape', async ({ baseURL }) => {
    const events = await collectSseEvents(baseURL!, { windowMs: 6000, maxEvents: 5 });
    expect(events.length, 'received at least one SSE event').toBeGreaterThan(0);

    const payload = events[events.length - 1];
    expect(typeof payload).toBe('object');
    const tickers = Object.keys(payload);
    expect(tickers.length, 'payload keyed by ticker').toBeGreaterThan(0);

    const entry = payload[tickers[0]];
    expect(entry).toMatchObject({
      ticker: expect.any(String),
      price: expect.any(Number),
      change: expect.any(Number),
      change_percent: expect.any(Number),
    });
    expect(['up', 'down', 'flat']).toContain(entry.direction);
    // previous_price and timestamp present
    expect(entry).toHaveProperty('previous_price');
    expect(entry).toHaveProperty('timestamp');
  });

  test('prices update across events (stream is live)', async ({ baseURL }) => {
    const events = await collectSseEvents(baseURL!, { windowMs: 8000, maxEvents: 20 });
    expect(events.length).toBeGreaterThan(1);
    // Find any ticker whose price differs between the first and last event.
    const first = events[0];
    const last = events[events.length - 1];
    const anyTicker = Object.keys(first)[0];
    const moved =
      Object.keys(first).some((t) => last[t] && first[t].price !== last[t].price) ||
      first[anyTicker]?.price !== last[anyTicker]?.price;
    expect(moved, 'at least one price moved across the stream window').toBeTruthy();
  });
});
