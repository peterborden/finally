import { test, expect } from '@playwright/test';
import { trade, waitForPrice } from '../support/api';

/** §5.3 GET /api/portfolio/history — snapshots oldest→newest, grows on trade. */

test.describe('@api portfolio history', () => {
  test('returns {snapshots:[{total_value, recorded_at}]}', async ({ request }) => {
    const res = await request.get('/api/portfolio/history');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('snapshots');
    expect(Array.isArray(body.snapshots)).toBeTruthy();
    for (const s of body.snapshots) {
      expect(typeof s.total_value).toBe('number');
      expect(typeof s.recorded_at).toBe('string');
    }
  });

  test('a trade records a new snapshot (§7: snapshot after each trade)', async ({ request }) => {
    await waitForPrice(request, 'MSFT');
    const before = (await (await request.get('/api/portfolio/history')).json()).snapshots.length;
    const t = await trade(request, 'MSFT', 'buy', 1);
    expect(t.ok()).toBeTruthy();
    const after = (await (await request.get('/api/portfolio/history')).json()).snapshots.length;
    expect(after).toBeGreaterThan(before);
    // cleanup
    await trade(request, 'MSFT', 'sell', 1);
  });

  test('snapshots are chronological (oldest→newest)', async ({ request }) => {
    const body = await (await request.get('/api/portfolio/history')).json();
    const times = body.snapshots.map((s: { recorded_at: string }) => Date.parse(s.recorded_at));
    const sorted = [...times].sort((a, b) => a - b);
    expect(times).toEqual(sorted);
  });
});
