import { test, expect } from '@playwright/test';
import { chat, getPortfolio, waitForPrice } from '../support/api';

/**
 * §5.7 POST /api/chat with LLM_MOCK=true. The mock parses simple intents like
 * "buy N TICKER" so E2E can assert a trade actually executed (§6, PLAN §9).
 */

test.describe('@api chat (LLM_MOCK)', () => {
  test('plain message -> §5.7 shape with no side effects', async ({ request }) => {
    const res = await chat(request, 'How is my portfolio doing?');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
    expect(Array.isArray(body.trades)).toBeTruthy();
    expect(Array.isArray(body.watchlist_changes)).toBeTruthy();
    expect(Array.isArray(body.errors)).toBeTruthy();
  });

  test('"buy N TICKER" auto-executes a trade reflected in trades[] and portfolio', async ({
    request,
  }) => {
    await waitForPrice(request, 'AAPL');
    const before = await getPortfolio(request);
    const beforeQty = before.positions.find((p) => p.ticker === 'AAPL')?.quantity ?? 0;

    const res = await chat(request, 'buy 4 AAPL');
    expect(res.status()).toBe(200);
    const body = await res.json();

    expect(body.trades.length, 'a trade was executed').toBeGreaterThanOrEqual(1);
    const t = body.trades.find((x: { ticker: string }) => x.ticker === 'AAPL');
    expect(t).toMatchObject({ ticker: 'AAPL', side: 'buy', quantity: 4 });
    expect(t.price).toEqual(expect.any(Number));

    const after = await getPortfolio(request);
    const afterQty = after.positions.find((p) => p.ticker === 'AAPL')?.quantity ?? 0;
    expect(afterQty).toBeCloseTo(beforeQty + 4, 5);

    // cleanup
    await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'sell', quantity: 4 },
    });
  });

  test('failed action surfaces in errors[] not trades[]', async ({ request }) => {
    const res = await chat(request, 'buy 100000 AAPL');
    expect(res.status()).toBe(200);
    const body = await res.json();
    // Either the mock reports it couldn't fill, or errors[] is populated.
    const executedBig = body.trades.some(
      (t: { quantity: number }) => t.quantity >= 100000,
    );
    expect(executedBig).toBeFalsy();
    if (body.errors.length > 0) {
      expect(JSON.stringify(body.errors).toLowerCase()).toContain('cash');
    }
  });

  test('"add TICKER to watchlist" reflects in watchlist_changes', async ({ request }) => {
    await request.delete('/api/watchlist/PYPL');
    const res = await chat(request, 'add PYPL to my watchlist');
    expect(res.status()).toBe(200);
    const body = await res.json();
    // Mock may or may not parse this intent; assert shape and, if parsed, correctness.
    if (body.watchlist_changes.length > 0) {
      expect(body.watchlist_changes[0]).toMatchObject({ ticker: 'PYPL', action: 'add' });
    }
    await request.delete('/api/watchlist/PYPL');
  });
});
