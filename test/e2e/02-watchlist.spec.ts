import { test, expect } from '@playwright/test';
import { testId } from '../support/selectors';
import { removeTicker } from '../support/api';

/** PLAN §12: add and remove a ticker from the watchlist via the UI. (§10) */

const EXTRA = 'PYPL';

test.describe('@e2e watchlist add/remove', () => {
  test.beforeEach(async ({ request, page }) => {
    await removeTicker(request, EXTRA); // clean slate via API
    await page.goto('/');
    await expect(page.getByTestId(testId.watchlist)).toBeVisible();
  });

  test.afterEach(async ({ request }) => {
    await removeTicker(request, EXTRA);
  });

  test('add a ticker: it appears in the watchlist', async ({ page }) => {
    const input = page.getByTestId(testId.addTickerInput);
    await input.fill(EXTRA);
    const addBtn = page.getByTestId(testId.addTickerButton);
    if (await addBtn.count()) {
      await addBtn.click();
    } else {
      await input.press('Enter');
    }

    const row = page.getByTestId(testId.watchlistRow(EXTRA));
    if (await row.count()) {
      await expect(row).toBeVisible({ timeout: 10_000 });
    } else {
      await expect(page.getByText(new RegExp(`\\b${EXTRA}\\b`)).first()).toBeVisible({
        timeout: 10_000,
      });
    }
  });

  test('remove a ticker: it disappears from the watchlist', async ({ page, request }) => {
    // Arrange: ensure present first (via API for determinism), reload.
    await request.post('/api/watchlist', { data: { ticker: EXTRA } });
    await page.reload();

    const remove = page.getByTestId(testId.removeTickerButton(EXTRA));
    if (await remove.count()) {
      await remove.click();
    } else {
      // Fallback: hover the row and click a delete control within it.
      const row = page.getByTestId(testId.watchlistRow(EXTRA));
      await row.hover();
      await row.getByRole('button').last().click();
    }

    await expect(page.getByTestId(testId.watchlistRow(EXTRA))).toHaveCount(0, { timeout: 10_000 });
  });
});
