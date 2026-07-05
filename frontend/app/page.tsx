'use client';

/**
 * The FinAlly terminal root — assembles all eight components into the
 * single-page, Bloomberg-style layout locked in 04-CONTEXT.md:
 *
 *   - Header (top bar): live total value / cash / connection dot.
 *   - Left column: Watchlist (drives `selectedTicker`).
 *   - Center: PriceChart for the selected ticker.
 *   - Right: collapsible ChatPanel.
 *   - Bottom band: PortfolioHeatmap + PnLChart + PositionsTable + TradeBar.
 *
 * `useLivePrices` is the single SSE subscription for the whole page — its
 * `prices`/`history`/`status` are threaded down into every component that
 * needs to tick live rather than each component opening its own stream.
 *
 * `watchlist`/`portfolio`/`pnlHistory` are fetched once on mount and then
 * re-fetched via `refreshWatchlist` / `refreshPortfolio` (bundled together
 * as `refreshAll`) whenever a trade (TradeBar) or chat turn (ChatPanel)
 * reports it executed an action, per 04-CONTEXT.md "Data & State".
 */

import { useCallback, useEffect, useState } from 'react';

import * as api from '../lib/api';
import type { Portfolio, Snapshot, WatchlistEntry } from '../lib/types';
import { useLivePrices } from '../lib/useLivePrices';

import ChatPanel from '../components/ChatPanel';
import Header from '../components/Header';
import { PnLChart } from '../components/PnLChart';
import { PortfolioHeatmap } from '../components/PortfolioHeatmap';
import PositionsTable from '../components/PositionsTable';
import PriceChart from '../components/PriceChart';
import TradeBar from '../components/TradeBar';
import Watchlist from '../components/Watchlist';

export default function Home() {
  const { prices, history, status } = useLivePrices();

  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [pnlHistory, setPnlHistory] = useState<Snapshot[]>([]);

  const refreshWatchlist = useCallback(async () => {
    try {
      const entries = await api.getWatchlist();
      setWatchlist(entries);
    } catch {
      // Transient fetch failure — keep the last-known watchlist rendered.
    }
  }, []);

  const refreshPortfolio = useCallback(async () => {
    try {
      const [nextPortfolio, nextHistory] = await Promise.all([
        api.getPortfolio(),
        api.getHistory(),
      ]);
      setPortfolio(nextPortfolio);
      setPnlHistory(nextHistory);
    } catch {
      // Transient fetch failure — keep the last-known portfolio rendered.
    }
  }, []);

  const refreshAll = useCallback(() => {
    void refreshWatchlist();
    void refreshPortfolio();
  }, [refreshWatchlist, refreshPortfolio]);

  // Initial load: watchlist + portfolio + history. The SSE stream is opened
  // independently by useLivePrices.
  useEffect(() => {
    void refreshWatchlist();
    void refreshPortfolio();
  }, [refreshWatchlist, refreshPortfolio]);

  // Default the main chart's selection to the first watchlist ticker once
  // the watchlist has loaded; never overrides a user's own selection.
  useEffect(() => {
    if (selectedTicker === null && watchlist.length > 0) {
      setSelectedTicker(watchlist[0].ticker);
    }
  }, [watchlist, selectedTicker]);

  const positions = portfolio?.positions ?? [];
  const selectedHistory = selectedTicker ? (history[selectedTicker] ?? []) : [];

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-base text-gray-200">
      <Header portfolio={portfolio} prices={prices} status={status} />

      <div className="flex min-h-0 flex-1">
        <aside className="w-72 shrink-0 border-r border-border-muted">
          <Watchlist
            entries={watchlist}
            prices={prices}
            history={history}
            selected={selectedTicker}
            onSelect={setSelectedTicker}
            onWatchlistChange={refreshWatchlist}
          />
        </aside>

        <section className="min-w-0 flex-1 p-2">
          <PriceChart ticker={selectedTicker} points={selectedHistory} />
        </section>

        <aside className="w-80 shrink-0 p-2">
          <ChatPanel onActions={refreshAll} />
        </aside>
      </div>

      <div className="grid h-64 shrink-0 grid-cols-3 gap-2 border-t border-border-muted p-2">
        <PortfolioHeatmap positions={positions} prices={prices} />
        <PnLChart history={pnlHistory} />
        <div className="overflow-y-auto rounded border border-border-muted bg-panel">
          <PositionsTable positions={positions} prices={prices} />
        </div>
      </div>

      <div className="shrink-0 border-t border-border-muted bg-panel">
        <TradeBar onTraded={refreshAll} />
      </div>
    </main>
  );
}
