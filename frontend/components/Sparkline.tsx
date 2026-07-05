'use client';

/**
 * Sparkline — hand-rolled inline SVG polyline for a ticker's accumulated
 * price history (no external charting dependency; this renders once per
 * watchlist row so it stays intentionally tiny).
 *
 * Per PLAN.md §10 / 04-CONTEXT.md "sparklines fill in progressively": with
 * fewer than 2 points there's nothing to draw a line between, so an empty
 * placeholder box is rendered instead until enough SSE ticks accumulate.
 */

export interface SparklinePoint {
  t: number;
  price: number;
}

export interface SparklineProps {
  points: SparklinePoint[];
  width?: number;
  height?: number;
  /** Override the auto up/down/flat color derived from first-vs-last price. */
  color?: string;
}

const UP_COLOR = '#3fb950';
const DOWN_COLOR = '#f85149';
const FLAT_COLOR = '#6b7280';

function buildPolylinePoints(points: SparklinePoint[], width: number, height: number): string {
  const prices = points.map((point) => point.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min;
  const stepX = width / (points.length - 1);

  return points
    .map((point, index) => {
      const x = index * stepX;
      // SVG y grows downward, so a higher price should render nearer the top.
      const y = range === 0 ? height / 2 : height - ((point.price - min) / range) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
}

export default function Sparkline({ points, width = 80, height = 24, color }: SparklineProps) {
  if (points.length < 2) {
    return (
      <div
        style={{ width, height }}
        className="rounded-sm border border-border-muted/40"
        aria-hidden="true"
      />
    );
  }

  const first = points[0].price;
  const last = points[points.length - 1].price;
  const lineColor = color ?? (last > first ? UP_COLOR : last < first ? DOWN_COLOR : FLAT_COLOR);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      role="img"
      aria-label="Price sparkline"
    >
      <polyline
        points={buildPolylinePoints(points, width, height)}
        fill="none"
        stroke={lineColor}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
