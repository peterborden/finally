import type { SparkPoint } from '@/lib/types';

interface SparklineProps {
  data: SparkPoint[];
  width?: number;
  height?: number;
  color?: string;
}

/**
 * Lightweight inline SVG sparkline. Kept dependency-free (and fast) since it
 * renders once per watchlist row on every tick. Colored by net direction over
 * the accumulated window.
 */
export function Sparkline({ data, width = 88, height = 24, color }: SparklineProps) {
  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} role="img" aria-label="sparkline (accumulating)" className="opacity-40">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="#30363d" strokeDasharray="2 3" strokeWidth={1} />
      </svg>
    );
  }

  const prices = data.map((d) => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const stepX = width / (data.length - 1);
  const pad = 2;
  const usableH = height - pad * 2;

  const points = prices.map((p, i) => {
    const x = i * stepX;
    const y = pad + (1 - (p - min) / span) * usableH;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });

  const rising = prices[prices.length - 1] >= prices[0];
  const stroke = color ?? (rising ? '#3fb950' : '#f85149');

  return (
    <svg width={width} height={height} role="img" aria-label="price sparkline" className="overflow-visible">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={stroke}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
