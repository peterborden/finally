'use client';

/**
 * PortfolioHeatmap — a recharts Treemap where each rectangle is a position,
 * sized by portfolio weight (quantity x live price) and colored by
 * unrealized P&L (green = profit, red = loss, opacity scaled by |pct|).
 *
 * Live prices from the SSE `PriceMap` take priority over the last-known
 * `current_price` on the position so the heatmap re-colors in real time
 * without waiting for a full /api/portfolio re-fetch.
 */

import { ResponsiveContainer, Treemap } from 'recharts';
import type { Position, PriceMap } from '../lib/types';

interface PortfolioHeatmapProps {
  positions: Position[];
  prices: PriceMap;
}

/** One treemap node: ticker name, sizing weight, and P&L for coloring. */
interface HeatmapNode {
  name: string;
  size: number;
  pnl: number;
  pctChange: number;
  [key: string]: unknown;
}

/** Clamp a fraction into [0, 1] for opacity scaling. */
function clampMagnitude(pct: number): number {
  const abs = Math.abs(pct);
  return Math.min(abs, 0.2) / 0.2;
}

/** Map a position + live price into a heatmap node. */
function toHeatmapNode(position: Position, prices: PriceMap): HeatmapNode {
  const livePrice = prices[position.ticker]?.price ?? position.current_price;
  const size = Math.max(position.quantity * livePrice, 0);
  const pnl = (livePrice - position.avg_cost) * position.quantity;
  const pctChange = position.avg_cost !== 0 ? livePrice / position.avg_cost - 1 : 0;

  return {
    name: position.ticker,
    size,
    pnl,
    pctChange,
  };
}

/** Custom cell renderer: colors by P&L sign, labels ticker + P&L when large enough. */
function HeatmapContent(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnl?: number;
  pctChange?: number;
}) {
  const { x = 0, y = 0, width = 0, height = 0, name = '', pnl = 0, pctChange = 0 } = props;

  const magnitude = clampMagnitude(pctChange);
  const baseColor = pnl >= 0 ? '63, 185, 80' : '248, 81, 73'; // up / down tokens as rgb
  const opacity = 0.35 + magnitude * 0.55;
  const showLabel = width > 48 && height > 28;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: `rgba(${baseColor}, ${opacity})`,
          stroke: '#2a2a3a',
          strokeWidth: 1,
        }}
      />
      {showLabel && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 6}
            textAnchor="middle"
            fill="#e6edf3"
            fontSize={12}
            fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
          >
            {name}
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 10}
            textAnchor="middle"
            fill="#e6edf3"
            fontSize={11}
            fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
          >
            {pnl >= 0 ? '+' : ''}
            {pnl.toFixed(2)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap({ positions, prices }: PortfolioHeatmapProps) {
  if (positions.length === 0) {
    return (
      <div
        data-testid="portfolio-heatmap"
        className="flex h-full min-h-[160px] items-center justify-center rounded border border-border-muted bg-panel text-sm text-gray-400"
      >
        No positions
      </div>
    );
  }

  const data = positions.map((position) => toHeatmapNode(position, prices));

  return (
    <div
      data-testid="portfolio-heatmap"
      className="h-full min-h-[160px] w-full rounded border border-border-muted bg-panel p-2"
    >
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={data}
          dataKey="size"
          aspectRatio={4 / 3}
          stroke="#2a2a3a"
          isAnimationActive={false}
          content={<HeatmapContent />}
        />
      </ResponsiveContainer>
    </div>
  );
}
