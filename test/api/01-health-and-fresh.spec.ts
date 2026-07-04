import { test, expect } from '@playwright/test';
import { getPortfolio, getWatchlist } from '../support/api';
import { SEED_TICKERS, STARTING_CASH } from '../support/selectors';

/**
 * §5.8 health, §5.1 portfolio fresh shape, §5.4 watchlist seed.
 * These assert the CONTRACT shape, not exact prices (prices are live/simulated).
 */

test.describe('@api health & fresh start', () => {
  test('GET /api/health -> {status:"ok"}', async ({ request }) => {
    const res = await request.get('/api/health');
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  test('GET /api/portfolio returns the §5.1 shape', async ({ request }) => {
    const pf = await getPortfolio(request);
    // Required numeric keys present
    for (const k of ['cash_balance', 'positions_value', 'total_value', 'total_unrealized_pnl']) {
      expect(typeof pf[k as keyof typeof pf], `key ${k}`).toBe('number');
    }
    expect(Array.isArray(pf.positions)).toBeTruthy();
    // total = cash + positions_value (allow float slop)
    expect(pf.total_value).toBeCloseTo(pf.cash_balance + pf.positions_value, 2);
    // Each position (if any) carries the full §5.1 shape
    for (const p of pf.positions) {
      expect(p).toMatchObject({
        ticker: expect.any(String),
        quantity: expect.any(Number),
        avg_cost: expect.any(Number),
        market_value: expect.any(Number),
        unrealized_pnl: expect.any(Number),
        unrealized_pnl_percent: expect.any(Number),
      });
      // current_price may be null per contract
      expect(p.current_price === null || typeof p.current_price === 'number').toBeTruthy();
    }
  });

  test('GET /api/watchlist returns the 10 seed tickers in §5.4 shape', async ({ request }) => {
    const wl = await getWatchlist(request);
    const tickers = wl.map((w) => w.ticker);
    for (const seed of SEED_TICKERS) {
      expect(tickers, `seed ${seed} present`).toContain(seed);
    }
    for (const item of wl) {
      expect(item).toHaveProperty('ticker');
      // Price fields nullable until first tick; when present, correct types
      for (const k of ['price', 'previous_price', 'change', 'change_percent']) {
        const v = item[k as keyof typeof item];
        expect(v === null || typeof v === 'number', `${item.ticker}.${k}`).toBeTruthy();
      }
      expect(
        item.direction === null || ['up', 'down', 'flat'].includes(item.direction as string),
        `${item.ticker}.direction`,
      ).toBeTruthy();
    }
  });

  test('fresh account: cash and total value are sane (~$10k with no positions)', async ({
    request,
  }) => {
    // Only meaningful on a fresh volume. When positions exist from prior specs,
    // assert the invariant instead of the literal.
    const pf = await getPortfolio(request);
    if (pf.positions.length === 0) {
      expect(pf.cash_balance).toBeCloseTo(STARTING_CASH, 2);
      expect(pf.total_value).toBeCloseTo(STARTING_CASH, 2);
    } else {
      expect(pf.total_value).toBeGreaterThan(0);
    }
  });
});
