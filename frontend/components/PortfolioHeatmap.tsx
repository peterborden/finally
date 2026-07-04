'use client';

import { ResponsiveContainer, Treemap } from 'recharts';
import { Panel } from './Panel';
import { fmtSignedMoney, fmtPercent } from '@/lib/format';
import type { Portfolio } from '@/lib/types';

interface HeatmapProps {
  portfolio: Portfolio | null;
  onSelect?: (ticker: string) => void;
}

interface Node {
  name: string;
  size: number;
  pnl: number;
  pnlPct: number;
}

/** Map a P&L% to a diverging red↔green fill. */
function colorFor(pnlPct: number): string {
  if (pnlPct === 0) return '#30363d';
  const mag = Math.min(Math.abs(pnlPct) / 5, 1); // saturate at ±5%
  if (pnlPct > 0) {
    // dark → bright green
    const g = Math.round(90 + mag * 120);
    return `rgb(35, ${g}, 60)`;
  }
  const r = Math.round(120 + mag * 120);
  return `rgb(${r}, 45, 45)`;
}

interface ContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnl?: number;
  pnlPct?: number;
  onSelect?: (ticker: string) => void;
}

function TreemapCell(props: ContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, pnl = 0, pnlPct = 0, onSelect } = props;
  const showText = width > 44 && height > 26;
  return (
    <g
      onClick={() => name && onSelect?.(name)}
      style={{ cursor: name ? 'pointer' : 'default', backgroundColor: colorFor(pnlPct) }}
      data-testid={name ? `heatmap-tile-${name}` : undefined}
    >
      <rect x={x} y={y} width={width} height={height} fill={colorFor(pnlPct)} stroke="#0d1117" strokeWidth={1} />
      {showText && name && (
        <>
          <text x={x + 5} y={y + 15} fill="#f0f6fc" fontSize={11} fontWeight={700}>
            {name}
          </text>
          <text x={x + 5} y={y + 28} fill="#f0f6fc" fontSize={9} opacity={0.85}>
            {fmtPercent(pnlPct)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap({ portfolio, onSelect }: HeatmapProps) {
  const positions = portfolio?.positions ?? [];
  const data: Node[] = positions
    .filter((p) => p.market_value > 0)
    .map((p) => ({
      name: p.ticker,
      size: p.market_value,
      pnl: p.unrealized_pnl,
      pnlPct: p.unrealized_pnl_percent,
    }));

  return (
    <Panel title="Allocation Heatmap" testId="portfolio-heatmap" bodyClassName="p-1">
      {data.length === 0 ? (
        <div className="flex h-full items-center justify-center text-xs text-flat">No positions to visualize.</div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data}
            dataKey="size"
            nameKey="name"
            stroke="#0d1117"
            isAnimationActive={false}
            content={<TreemapCell onSelect={onSelect} />}
          />
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

export { colorFor };
