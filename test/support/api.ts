import { APIRequestContext, expect } from '@playwright/test';

/**
 * Thin typed wrappers around the §5 REST API. Used directly by the `api` project
 * and as setup/teardown/reset helpers by the `e2e` project so UI specs start from
 * a known state without depending on UI to arrange it.
 */

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  positions_value: number;
  total_value: number;
  total_unrealized_pnl: number;
  positions: Position[];
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: 'up' | 'down' | 'flat' | null;
}

export async function getPortfolio(req: APIRequestContext): Promise<Portfolio> {
  const res = await req.get('/api/portfolio');
  expect(res.ok(), `GET /api/portfolio -> ${res.status()}`).toBeTruthy();
  return res.json();
}

export async function getWatchlist(req: APIRequestContext): Promise<WatchlistItem[]> {
  const res = await req.get('/api/watchlist');
  expect(res.ok(), `GET /api/watchlist -> ${res.status()}`).toBeTruthy();
  return (await res.json()).watchlist;
}

export async function trade(
  req: APIRequestContext,
  ticker: string,
  side: 'buy' | 'sell',
  quantity: number,
) {
  return req.post('/api/portfolio/trade', { data: { ticker, side, quantity } });
}

export async function addTicker(req: APIRequestContext, ticker: string) {
  return req.post('/api/watchlist', { data: { ticker } });
}

export async function removeTicker(req: APIRequestContext, ticker: string) {
  return req.delete(`/api/watchlist/${ticker}`);
}

export async function chat(req: APIRequestContext, message: string) {
  return req.post('/api/chat', { data: { message } });
}

/**
 * Wait until the price cache has a non-null price for `ticker`. Trades require a
 * live price, and the simulator ticks ~every 500ms, so a fresh container may need
 * a moment before the first tick lands. Polls the watchlist API.
 */
export async function waitForPrice(
  req: APIRequestContext,
  ticker: string,
  timeoutMs = 20_000,
): Promise<number> {
  const deadline = Date.now() + timeoutMs;
  let last: number | null = null;
  while (Date.now() < deadline) {
    const wl = await getWatchlist(req);
    const item = wl.find((w) => w.ticker === ticker.toUpperCase());
    if (item && item.price != null && item.price > 0) return item.price;
    last = item?.price ?? null;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timed out waiting for a price on ${ticker} (last=${last})`);
}

/**
 * Best-effort reset of the single-user account to a clean-ish baseline so a spec
 * can run repeatably against a persisted DB: sell every open position back to the
 * cache. Does not reset cash to exactly $10k (trades realize P&L) — specs that need
 * an exact starting cash should assert relatively or run against a fresh volume.
 */
export async function flattenPositions(req: APIRequestContext): Promise<void> {
  const pf = await getPortfolio(req);
  for (const pos of pf.positions) {
    if (pos.quantity > 0) {
      await trade(req, pos.ticker, 'sell', pos.quantity);
    }
  }
}
