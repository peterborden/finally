'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/Header';
import { Watchlist } from '@/components/Watchlist';
import { MainChart } from '@/components/MainChart';
import { PortfolioHeatmap } from '@/components/PortfolioHeatmap';
import { PnLChart } from '@/components/PnLChart';
import { PositionsTable } from '@/components/PositionsTable';
import { TradeBar } from '@/components/TradeBar';
import { ChatPanel } from '@/components/ChatPanel';
import { usePriceStream } from '@/lib/usePriceStream';
import { useWatchlist } from '@/lib/useWatchlist';
import { usePortfolio } from '@/lib/usePortfolio';

export default function Dashboard() {
  const { prices, sparklines, status } = usePriceStream();
  const { items, add, remove, refresh: refreshWatchlist } = useWatchlist();
  const { portfolio, history, refresh: refreshPortfolio } = usePortfolio();

  const [selected, setSelected] = useState<string | null>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);

  // Default the selected ticker to the first watchlist entry once loaded.
  useEffect(() => {
    if (!selected && items.length > 0) setSelected(items[0].ticker);
  }, [items, selected]);

  const selectedQuote = selected ? prices[selected] : undefined;
  const selectedSeries = selected ? sparklines[selected] ?? [] : [];

  function afterActions() {
    refreshPortfolio();
    refreshWatchlist();
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header portfolio={portfolio} status={status} />

      <div className="flex min-h-0 flex-1">
        {/* Left: watchlist */}
        <div className="hidden w-72 shrink-0 border-r border-border-subtle p-2 md:block">
          <Watchlist
            items={items}
            prices={prices}
            sparklines={sparklines}
            selected={selected}
            onSelect={setSelected}
            onAdd={add}
            onRemove={remove}
          />
        </div>

        {/* Center: charts + positions + trade bar */}
        <div className="flex min-w-0 flex-1 flex-col gap-2 p-2">
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-3">
            <div className="min-h-0 lg:col-span-2">
              <MainChart ticker={selected} quote={selectedQuote} series={selectedSeries} />
            </div>
            <div className="grid min-h-0 grid-rows-2 gap-2">
              <PortfolioHeatmap portfolio={portfolio} onSelect={setSelected} />
              <PnLChart snapshots={history} />
            </div>
          </div>

          <div className="h-56 shrink-0">
            <PositionsTable portfolio={portfolio} onSelect={setSelected} />
          </div>

          <TradeBar prices={prices} selected={selected} onTraded={afterActions} />
        </div>

        {/* Right: AI chat */}
        <ChatPanel
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed((c) => !c)}
          onActions={afterActions}
        />
      </div>
    </div>
  );
}
