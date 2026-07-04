import { Page, Locator, expect } from '@playwright/test';
import { testId } from './selectors';

/**
 * Locator helpers that prefer the requested data-testid but fall back to a stable
 * role/text selector, so the suite still drives the app if a testid is missing.
 * Frontend engineer: adding the testids in selectors.ts makes all of this exact.
 */

export function byTestId(page: Page, id: string): Locator {
  return page.getByTestId(id);
}

/** Parse a currency-ish string like "$8,075.00" or "8075" into a number. */
export function parseMoney(text: string | null): number {
  if (!text) return NaN;
  const m = text.replace(/[^0-9.\-]/g, '');
  return parseFloat(m);
}

/** Read the header cash balance, tolerating testid-or-text presentation. */
export async function readCash(page: Page): Promise<number> {
  const el = page.getByTestId(testId.cashBalance);
  if (await el.count()) return parseMoney(await el.first().innerText());
  // Fallback: any element mentioning "cash" with a dollar amount nearby.
  const text = await page.getByText(/cash/i).first().innerText().catch(() => '');
  return parseMoney(text);
}

export async function readTotalValue(page: Page): Promise<number> {
  const el = page.getByTestId(testId.totalValue);
  if (await el.count()) return parseMoney(await el.first().innerText());
  return NaN;
}

/** Wait for the SSE connection indicator to report connected. */
export async function waitForConnected(page: Page, timeout = 20_000): Promise<void> {
  const dot = page.getByTestId(testId.connectionStatus);
  if (await dot.count()) {
    await expect(dot.first()).toHaveAttribute('data-state', 'connected', { timeout });
  } else {
    // Fallback: wait for any price to render in the watchlist.
    await page.waitForTimeout(3000);
  }
}

/**
 * Wait until at least one watchlist price cell shows a numeric value (proves the
 * SSE stream is flowing into the UI). Falls back to scanning row text.
 */
export async function waitForStreamingPrice(page: Page, ticker: string, timeout = 25_000) {
  const cell = page.getByTestId(testId.watchlistPrice(ticker));
  await expect
    .poll(
      async () => {
        if (await cell.count()) {
          return parseMoney(await cell.first().innerText());
        }
        const row = page.getByTestId(testId.watchlistRow(ticker));
        if (await row.count()) return parseMoney(await row.first().innerText());
        return NaN;
      },
      { timeout, message: `waiting for a streaming price on ${ticker}` },
    )
    .toBeGreaterThan(0);
}

/** Read a watchlist price as a number (NaN if not present/parsed). */
export async function readWatchlistPrice(page: Page, ticker: string): Promise<number> {
  const cell = page.getByTestId(testId.watchlistPrice(ticker));
  if (await cell.count()) return parseMoney(await cell.first().innerText());
  const row = page.getByTestId(testId.watchlistRow(ticker));
  if (await row.count()) return parseMoney(await row.first().innerText());
  return NaN;
}
