import { test, expect, type Page } from '@playwright/test';

/**
 * FinAlly E2E suite (PLAN.md §12), run under LLM_MOCK=true against a
 * running `finally` container.
 *
 * Scenarios run serially in one `describe.serial` block because several
 * assume the outcome of a prior scenario (a MSFT position exists after
 * "buy shares", which "portfolio visualizations" and "sell shares" then
 * build on). Each test still navigates fresh (`page.goto('/')`) so
 * frontend state is never carried between tests -- only backend state
 * (positions/cash/watchlist persisted in SQLite) is shared, matching how
 * a real user's session would behave across reloads.
 *
 * The default watchlist/seed data (PLAN.md §7): 10 tickers, $10,000 cash.
 */

const DEFAULT_TICKERS = [
  'AAPL',
  'GOOGL',
  'MSFT',
  'AMZN',
  'TSLA',
  'NVDA',
  'META',
  'JPM',
  'V',
  'NFLX',
];

/** Read the value rendered next to a Header label ("Total Value" / "Cash"). */
async function readHeaderValue(page: Page, label: string): Promise<string> {
  const labelNode = page.getByText(label, { exact: true });
  const valueNode = labelNode.locator('xpath=following-sibling::div[1]');
  return (await valueNode.innerText()).trim();
}

/** Ensure the collapsible AI chat panel is expanded, then return its input. */
async function openChatPanel(page: Page) {
  const expandButton = page.getByRole('button', { name: 'Expand AI chat panel' });
  if (await expandButton.isVisible().catch(() => false)) {
    await expandButton.click();
  }
  return page.getByPlaceholder('Ask FinAlly...');
}

test.describe.serial('FinAlly trading workstation', () => {
  test('fresh start: default watchlist, $10k cash, streaming prices', async ({ page }) => {
    await page.goto('/');

    // All 10 default tickers are present in the watchlist.
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByText(ticker, { exact: true })).toBeVisible();
    }

    // $10,000.00 cash (and, with no positions yet, total value equals cash).
    await expect
      .poll(async () => readHeaderValue(page, 'Cash'), { timeout: 15_000 })
      .toBe('$10,000.00');
    await expect
      .poll(async () => readHeaderValue(page, 'Total Value'), { timeout: 15_000 })
      .toBe('$10,000.00');

    // Prices are streaming: the SSE connection reaches "Connected".
    await expect
      .poll(
        async () => page.getByRole('status').getAttribute('aria-label'),
        { timeout: 15_000 },
      )
      .toContain('Connected');
  });

  test('add and remove a watchlist ticker', async ({ page }) => {
    await page.goto('/');

    await page.getByLabel('Add ticker').fill('PYPL');
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.getByText('PYPL', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Remove PYPL' }).click();
    await expect(page.getByText('PYPL', { exact: true })).not.toBeVisible();
  });

  test('buy shares: cash decreases and a position appears', async ({ page }) => {
    await page.goto('/');

    const cashBefore = await readHeaderValue(page, 'Cash');

    await page.getByPlaceholder('AAPL').fill('MSFT');
    await page.getByPlaceholder('10').fill('5');
    await page.getByRole('button', { name: 'Buy', exact: true }).click();

    await expect
      .poll(async () => readHeaderValue(page, 'Cash'), { timeout: 15_000 })
      .not.toBe(cashBefore);

    await expect(page.getByRole('cell', { name: 'MSFT', exact: true })).toBeVisible();
    await expect(page.getByRole('row', { name: /MSFT/ })).toContainText('5');
  });

  test('portfolio visualizations render', async ({ page }) => {
    await page.goto('/');

    // Heatmap: with a position held, the empty state is gone and the
    // recharts Treemap (an <svg>) is rendered inside the hook.
    const heatmap = page.getByTestId('portfolio-heatmap');
    await expect(heatmap).toBeVisible();
    await expect(heatmap).not.toContainText('No positions');
    await expect(heatmap.locator('svg')).toBeVisible();

    // P&L chart: lightweight-charts draws onto a <canvas> inside the hook.
    const pnlChart = page.getByTestId('pnl-chart');
    await expect(pnlChart).toBeVisible();
    await expect(pnlChart.locator('canvas').first()).toBeVisible();

    // Positions table shows the MSFT position from the prior test.
    await expect(page.getByRole('cell', { name: 'MSFT', exact: true })).toBeVisible();
  });

  test('sell shares: cash increases and quantity decreases', async ({ page }) => {
    await page.goto('/');

    const cashBefore = await readHeaderValue(page, 'Cash');

    await page.getByPlaceholder('AAPL').fill('MSFT');
    await page.getByPlaceholder('10').fill('2');
    await page.getByRole('button', { name: 'Sell', exact: true }).click();

    await expect
      .poll(async () => readHeaderValue(page, 'Cash'), { timeout: 15_000 })
      .not.toBe(cashBefore);

    // 5 bought, 2 sold -> 3 remain.
    await expect(page.getByRole('row', { name: /MSFT/ })).toContainText('3');
  });

  test('AI chat (mocked) drives a trade inline', async ({ page }) => {
    await page.goto('/');

    const chatInput = await openChatPanel(page);
    await chatInput.fill('Please buy some shares for me [[buy:AAPL:2]]');
    await page.getByRole('button', { name: 'Send', exact: true }).click();

    // The deterministic mock reply and its inline action confirmation.
    await expect(page.getByText(/\[mock\] Executed/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Filled .*AAPL/i)).toBeVisible();

    // The portfolio reflects the new AAPL position.
    await page.goto('/');
    await expect(page.getByRole('cell', { name: 'AAPL', exact: true })).toBeVisible();
  });

  test('SSE reconnect resilience', async ({ page, context }) => {
    await page.goto('/');

    await expect
      .poll(
        async () => page.getByRole('status').getAttribute('aria-label'),
        { timeout: 15_000 },
      )
      .toContain('Connected');

    const priceCell = page
      .locator('li', { hasText: 'AAPL' })
      .locator('div')
      .nth(1);
    const priceBefore = await priceCell.innerText();

    // Simulate a transient network drop: EventSource surfaces this via
    // onerror -> status flips off "Connected" while offline.
    await context.setOffline(true);
    await expect
      .poll(
        async () => page.getByRole('status').getAttribute('aria-label'),
        { timeout: 15_000 },
      )
      .not.toContain('Connected');

    await context.setOffline(false);

    // EventSource auto-retries (server sends `retry: 1000`); connection
    // should recover and prices resume updating.
    await expect
      .poll(
        async () => page.getByRole('status').getAttribute('aria-label'),
        { timeout: 20_000 },
      )
      .toContain('Connected');

    await expect
      .poll(async () => priceCell.innerText(), { timeout: 15_000 })
      .not.toBe(priceBefore);
  });
});
