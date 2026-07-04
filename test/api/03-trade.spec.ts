import { test, expect } from '@playwright/test';
import { getPortfolio, trade, waitForPrice } from '../support/api';

/** §5.2 trade success + validation-failure shapes; portfolio invariants. */

const TICKER = 'AAPL';

test.describe('@api trade execution', () => {
  test('buy: 200, §5.2 success shape, cash down, position appears', async ({ request }) => {
    await waitForPrice(request, TICKER);
    const before = await getPortfolio(request);

    const res = await trade(request, TICKER, 'buy', 2);
    expect(res.status(), 'buy returns 200').toBe(200);
    const body = await res.json();

    expect(body.success).toBe(true);
    expect(body.error).toBeNull();
    expect(body.trade).toMatchObject({
      ticker: TICKER,
      side: 'buy',
      quantity: 2,
      price: expect.any(Number),
    });
    expect(body.trade.executed_at).toBeTruthy();
    expect(body.position).toMatchObject({ ticker: TICKER, quantity: expect.any(Number) });
    expect(typeof body.cash_balance).toBe('number');

    // Cash decreased by ~ price*qty
    const cost = body.trade.price * 2;
    expect(body.cash_balance).toBeCloseTo(before.cash_balance - cost, 1);

    const after = await getPortfolio(request);
    const pos = after.positions.find((p) => p.ticker === TICKER);
    expect(pos, 'position exists after buy').toBeTruthy();
    expect(pos!.quantity).toBeGreaterThanOrEqual(2);
  });

  test('sell: 200, cash up, position reduced/removed', async ({ request }) => {
    await waitForPrice(request, TICKER);
    // Ensure we own something to sell.
    await trade(request, TICKER, 'buy', 3);
    const before = await getPortfolio(request);
    const held = before.positions.find((p) => p.ticker === TICKER)!.quantity;

    const res = await trade(request, TICKER, 'sell', held);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.trade.side).toBe('sell');
    expect(body.cash_balance).toBeGreaterThan(before.cash_balance);

    const after = await getPortfolio(request);
    const pos = after.positions.find((p) => p.ticker === TICKER);
    // Fully sold -> row gone (§4: position None when fully sold)
    expect(pos === undefined || pos.quantity === 0).toBeTruthy();
  });

  test('buy with insufficient cash -> 400 {detail}', async ({ request }) => {
    await waitForPrice(request, TICKER);
    const res = await trade(request, TICKER, 'buy', 1_000_000);
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body).toHaveProperty('detail');
    expect(String(body.detail).toLowerCase()).toContain('cash');
  });

  test('sell more shares than owned -> 400 {detail}', async ({ request }) => {
    const res = await trade(request, 'NFLX', 'sell', 999999);
    expect(res.status()).toBe(400);
    expect(await res.json()).toHaveProperty('detail');
  });

  test('non-positive quantity -> 400', async ({ request }) => {
    const res = await trade(request, TICKER, 'buy', 0);
    expect(res.status()).toBe(400);
  });
});
