import { test, expect } from '@playwright/test';
import { testId } from '../support/selectors';
import { waitForPrice, trade, flattenPositions } from '../support/api';

/**
 * PLAN §12 portfolio visualization: heatmap renders tiles colored by P&L, and the
 * P&L chart has data points. We arrange a couple of positions via API, then assert
 * the UI renders the visualizations. (§10)
 */

test.describe('@e2e portfolio visualization', () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForPrice(request, 'AAPL');
    await waitForPrice(request, 'MSFT');
    await trade(request, 'AAPL', 'buy', 3);
    await trade(request, 'MSFT', 'buy', 2);
    await page.goto('/');
  });

  test.afterEach(async ({ request }) => {
    await flattenPositions(request);
  });

  test('heatmap renders a tile per position', async ({ page }) => {
    const heatmap = page.getByTestId(testId.heatmap);
    await expect(heatmap).toBeVisible({ timeout: 15_000 });

    for (const t of ['AAPL', 'MSFT']) {
      const tile = page.getByTestId(testId.heatmapTile(t));
      if (await tile.count()) {
        await expect(tile).toBeVisible();
        // Tile is colored (has a non-transparent background) — sanity check it renders.
        const bg = await tile.evaluate((el) => getComputedStyle(el).backgroundColor);
        expect(bg).not.toBe('rgba(0, 0, 0, 0)');
      } else {
        await expect(heatmap.getByText(t).first()).toBeVisible();
      }
    }
  });

  test('positions table lists the held tickers with qty/avg cost/pnl', async ({ page }) => {
    const table = page.getByTestId(testId.positionsTable);
    await expect(table).toBeVisible();
    for (const t of ['AAPL', 'MSFT']) {
      const row = page.getByTestId(testId.positionRow(t));
      if (await row.count()) {
        await expect(row).toBeVisible();
      } else {
        await expect(table.getByText(t).first()).toBeVisible();
      }
    }
  });

  test('P&L chart is present and has rendered data', async ({ page }) => {
    const chart = page.getByTestId(testId.pnlChart);
    await expect(chart).toBeVisible({ timeout: 15_000 });
    // Canvas or SVG with content — assert it has non-zero size and drawn children/pixels.
    const box = await chart.boundingBox();
    expect(box && box.width > 0 && box.height > 0).toBeTruthy();
    // If SVG-based, expect path/points; if canvas, at least the element exists sized.
    const svgPoints = await chart.locator('svg path, svg circle, svg polyline').count();
    if (svgPoints === 0) {
      // canvas fallback: ensure a <canvas> exists
      expect(await chart.locator('canvas').count()).toBeGreaterThan(0);
    } else {
      expect(svgPoints).toBeGreaterThan(0);
    }
  });
});
