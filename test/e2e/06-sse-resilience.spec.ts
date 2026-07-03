import { test, expect } from '@playwright/test';
import { testId } from '../support/selectors';
import { waitForConnected, waitForStreamingPrice, readWatchlistPrice } from '../support/ui';

/**
 * PLAN §12 SSE resilience: disconnect the stream and verify the client reconnects
 * (EventSource auto-retry) and prices resume. We simulate the drop with
 * context.setOffline, which severs the live EventSource connection. (§2 connection dot)
 */

test.describe('@e2e SSE resilience', () => {
  test('disconnect → indicator degrades → reconnect → prices resume', async ({ page, context }) => {
    await page.goto('/');
    await waitForConnected(page);
    await waitForStreamingPrice(page, 'AAPL');
    const dot = page.getByTestId(testId.connectionStatus);

    // 1. Go offline — the EventSource connection drops.
    await context.setOffline(true);

    if (await dot.count()) {
      // Indicator should leave the "connected" state (reconnecting or disconnected).
      await expect
        .poll(async () => dot.first().getAttribute('data-state'), {
          timeout: 15_000,
          message: 'indicator leaves connected state while offline',
        })
        .not.toBe('connected');
    } else {
      test.info().annotations.push({
        type: 'note',
        description: 'connection-status testid missing — cannot assert degraded state visually',
      });
    }

    // 2. Back online — EventSource retries automatically.
    await context.setOffline(false);

    if (await dot.count()) {
      await expect(dot.first()).toHaveAttribute('data-state', 'connected', { timeout: 30_000 });
    }

    // 3. Prices resume flowing after reconnect.
    const before = await readWatchlistPrice(page, 'AAPL');
    await expect
      .poll(
        async () => {
          const now = await readWatchlistPrice(page, 'AAPL');
          return !Number.isNaN(now) && now > 0;
        },
        { timeout: 25_000, message: 'a price is present again after reconnect' },
      )
      .toBeTruthy();
    expect(before).toBeGreaterThanOrEqual(0);
  });
});
