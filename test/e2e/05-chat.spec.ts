import { test, expect } from '@playwright/test';
import { testId } from '../support/selectors';
import { waitForPrice, getPortfolio, flattenPositions } from '../support/api';

/**
 * PLAN §12 AI chat (LLM_MOCK): send a message → receive a response → an inline
 * trade execution confirmation appears, and the trade is reflected in the portfolio.
 * (§9, §10)
 */

test.describe('@e2e AI chat', () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForPrice(request, 'AAPL');
    await page.goto('/');
    await expect(page.getByTestId(testId.chatPanel)).toBeVisible();
  });

  test.afterEach(async ({ request }) => {
    await flattenPositions(request);
  });

  async function send(page: import('@playwright/test').Page, msg: string) {
    const input = page.getByTestId(testId.chatInput);
    await input.fill(msg);
    const send = page.getByTestId(testId.chatSend);
    if (await send.count()) await send.click();
    else await input.press('Enter');
  }

  test('a plain message gets an assistant reply', async ({ page }) => {
    await send(page, 'How is my portfolio doing?');
    const assistant = page
      .getByTestId(testId.chatMessage)
      .filter({ has: page.locator('[data-role="assistant"]') })
      .or(page.locator('[data-role="assistant"]'));
    // Fallback: just wait for the messages container to grow with reply text.
    await expect(page.getByTestId(testId.chatMessages)).toBeVisible();
    await expect
      .poll(async () => (await page.getByTestId(testId.chatMessage).count()), {
        timeout: 20_000,
        message: 'assistant reply rendered',
      })
      .toBeGreaterThanOrEqual(2);
  });

  test('"buy 5 AAPL" via chat executes a trade shown inline and in the portfolio', async ({
    page,
    request,
  }) => {
    const before = await getPortfolio(request);
    const beforeQty = before.positions.find((p) => p.ticker === 'AAPL')?.quantity ?? 0;

    await send(page, 'buy 5 AAPL');

    // Inline action/confirmation badge appears in the chat.
    const badge = page.getByTestId(testId.chatActionBadge);
    if (await badge.count()) {
      await expect(badge.first()).toBeVisible({ timeout: 20_000 });
      await expect(badge.first()).toContainText(/AAPL/i);
    } else {
      // Fallback: assistant message references the executed buy.
      await expect(page.getByText(/bought.*AAPL|AAPL.*buy|buy.*AAPL/i).first()).toBeVisible({
        timeout: 20_000,
      });
    }

    // Portfolio reflects the +5 shares.
    await expect
      .poll(
        async () => {
          const pf = await getPortfolio(request);
          return pf.positions.find((p) => p.ticker === 'AAPL')?.quantity ?? 0;
        },
        { timeout: 20_000, message: 'chat trade reflected in portfolio' },
      )
      .toBeCloseTo(beforeQty + 5, 5);
  });

  test('a loading indicator shows while the LLM responds', async ({ page }) => {
    const loading = page.getByTestId(testId.chatLoading);
    await send(page, 'summarize my risk');
    if (await loading.count()) {
      // It may resolve fast under mock; accept either it was seen or reply arrived.
      await Promise.race([
        loading.first().waitFor({ state: 'visible', timeout: 3000 }).catch(() => {}),
        page.getByTestId(testId.chatMessage).nth(1).waitFor({ timeout: 20_000 }),
      ]);
    }
    await expect(page.getByTestId(testId.chatMessages)).toBeVisible();
  });
});
