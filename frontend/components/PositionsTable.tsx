'use client';

import { Panel } from './Panel';
import { fmtMoney, fmtPrice, fmtQty, fmtSignedMoney, fmtPercent, pnlColor } from '@/lib/format';
import type { Portfolio } from '@/lib/types';

interface PositionsTableProps {
  portfolio: Portfolio | null;
  onSelect?: (ticker: string) => void;
}

export function PositionsTable({ portfolio, onSelect }: PositionsTableProps) {
  const positions = portfolio?.positions ?? [];
  return (
    <Panel title="Positions" bodyClassName="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-bg-panel text-[10px] uppercase tracking-wider text-flat">
          <tr className="border-b border-border-subtle">
            <th className="py-1 pl-3 text-left font-medium">Symbol</th>
            <th className="px-2 text-right font-medium">Qty</th>
            <th className="px-2 text-right font-medium">Avg Cost</th>
            <th className="px-2 text-right font-medium">Price</th>
            <th className="px-2 text-right font-medium">Mkt Value</th>
            <th className="px-2 text-right font-medium">Unrl P&L</th>
            <th className="pr-3 text-right font-medium">%</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-flat">
                No open positions. Use the trade bar or the AI assistant to buy.
              </td>
            </tr>
          )}
          {positions.map((p) => (
            <tr
              key={p.ticker}
              onClick={() => onSelect?.(p.ticker)}
              data-testid={`pos-row-${p.ticker}`}
              className="cursor-pointer border-b border-border-muted tabular-nums hover:bg-bg-hover"
            >
              <td className="py-1.5 pl-3 text-left font-semibold text-gray-100">{p.ticker}</td>
              <td className="px-2 text-right">{fmtQty(p.quantity)}</td>
              <td className="px-2 text-right">{fmtPrice(p.avg_cost)}</td>
              <td className="px-2 text-right">{fmtPrice(p.current_price)}</td>
              <td className="px-2 text-right">{fmtMoney(p.market_value)}</td>
              <td className={`px-2 text-right ${pnlColor(p.unrealized_pnl)}`}>{fmtSignedMoney(p.unrealized_pnl)}</td>
              <td className={`pr-3 text-right ${pnlColor(p.unrealized_pnl)}`}>{fmtPercent(p.unrealized_pnl_percent)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
