import { test, expect } from '@playwright/test';
import { testId } from '../support/selectors';
import { waitForPrice, getPortfolio } from '../support/api';
import { readCash } from '../support/ui';

/**
 * PLAN §12: buy (cash down, position appears, portfolio updates) and
 * sell (cash up, position updates/disappears) via the trade bar. (§10)
 */

const TICKER = 'AAPL';

async function submitTrade(page: import('@playwright/test').Page, ticker: string, qty: number, side: 'buy' | 'sell') {
  await page.getByTestId(testId.tradeTickerInput).fill(ticker);
  await page.getByTestId(testId.tradeQtyInput).fill(String(qty));
  await page.getByTestId(side === 'buy' ? testId.tradeBuyButton : testId.tradeSellButton).click();
}

test.describe('@e2e trading via the trade bar', () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForPrice(request, TICKER);
    await page.goto('/');
    await expect(page.getByTestId(testId.tradeBar)).toBeVisible();
  });

  test('buy: cash decreases and a position row appears', async ({ page, request }) => {
    const cashBefore = await readCash(page);

    await submitTrade(page, TICKER, 2, 'buy');

    // Position row shows up in the positions table.
    const posRow = page.getByTestId(testId.positionRow(TICKER));
    if (await posRow.count()) {
      await expect(posRow).toBeVisible({ timeout: 10_000 });
    } else {
      await expect(page.getByTestId(testId.positionsTable).getByText(TICKER).first()).toBeVisible({
        timeout: 10_000,
      });
    }

    // Cash decreased (assert via UI, corroborate via API).
    await expect
      .poll(() => readCash(page), { timeout: 10_000, message: 'header cash decreased' })
      .toBeLessThan(cashBefore);

    const pf = await getPortfolio(request);
    expect(pf.positions.find((p) => p.ticker === TICKER)?.quantity ?? 0).toBeGreaterThanOrEqual(2);

    // cleanup
    await request.post('/api/portfolio/trade', { data: { ticker: TICKER, side: 'sell', quantity: pf.positions.find((p) => p.ticker === TICKER)!.quantity } });
  });

  test('sell: cash increases and position reduces/disappears', async ({ page, request }) => {
    // Arrange holdings via API for determinism.
    await request.post('/api/portfolio/trade', { data: { ticker: TICKER, side: 'buy', quantity: 3 } });
    await page.reload();
    const cashBefore = await readCash(page);

    await submitTrade(page, TICKER, 3, 'sell');

    await expect
      .poll(() => readCash(page), { timeout: 10_000, message: 'header cash increased' })
      .toBeGreaterThan(cashBefore);

    const pf = await getPortfolio(request);
    const pos = pf.positions.find((p) => p.ticker === TICKER);
    expect(pos === undefined || pos.quantity === 0).toBeTruthy();
    // Row should be gone from the table.
    await expect(page.getByTestId(testId.positionRow(TICKER))).toHaveCount(0, { timeout: 10_000 });
  });
});
