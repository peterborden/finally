import { test, expect } from '@playwright/test';
import { getWatchlist, addTicker, removeTicker } from '../support/api';

/** §5.5 POST (201), §5.6 DELETE (200 / 404). */

const EXTRA = 'PYPL';

test.describe('@api watchlist CRUD', () => {
  test.beforeAll(async ({ request }) => {
    // Clean any residue from a prior run so the add asserts a real state change.
    await removeTicker(request, EXTRA);
  });

  test('POST /api/watchlist adds a ticker -> 201 with §5.4 item shape', async ({ request }) => {
    const res = await addTicker(request, EXTRA);
    expect(res.status(), 'add returns 201').toBe(201);
    const item = await res.json();
    expect(item.ticker).toBe(EXTRA);
    for (const k of ['price', 'previous_price', 'change', 'change_percent']) {
      const v = item[k];
      expect(v === null || typeof v === 'number', k).toBeTruthy();
    }

    const wl = await getWatchlist(request);
    expect(wl.map((w) => w.ticker)).toContain(EXTRA);
  });

  test('ticker is normalized to uppercase', async ({ request }) => {
    await removeTicker(request, 'sofi');
    const res = await addTicker(request, 'sofi');
    expect([200, 201]).toContain(res.status());
    const item = await res.json();
    expect(item.ticker).toBe('SOFI');
    await removeTicker(request, 'SOFI');
  });

  test('DELETE /api/watchlist/{ticker} removes -> {removed:true}', async ({ request }) => {
    const res = await removeTicker(request, EXTRA);
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ removed: true });

    const wl = await getWatchlist(request);
    expect(wl.map((w) => w.ticker)).not.toContain(EXTRA);
  });

  test('DELETE of an absent ticker -> 404', async ({ request }) => {
    const res = await removeTicker(request, 'ZZZZ');
    expect(res.status()).toBe(404);
  });
});
