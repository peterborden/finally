'use client';

/**
 * PriceChart — main chart area: a lightweight-charts line series for the
 * currently selected ticker, built from ticks accumulated by
 * `useLivePrices` since page load (no server-side historical data — see
 * PLAN.md §10 / 04-CONTEXT.md "Deferred").
 *
 * lightweight-charts v5 note: series are created via
 * `chart.addSeries(LineSeries, options)` (LineSeries imported from the
 * package) — v4's `chart.addLineSeries()` was removed in v5.
 *
 * The chart instance is created once on mount and disposed on unmount; the
 * series data is replaced whenever `ticker`/`points` change (cleared to an
 * empty series when there's no selection or no ticks yet), so switching
 * tickers doesn't tear down and recreate the underlying chart/canvas.
 */

import { useEffect, useRef } from 'react';
import {
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { HistoryPoint } from '../lib/useLivePrices';

export interface PriceChartProps {
  ticker: string | null;
  points: HistoryPoint[];
}

/**
 * lightweight-charts requires strictly ascending series time values.
 * Backend timestamps are `time.time()` floats (seconds) that should already
 * be increasing tick-to-tick, but any non-increasing entry is dropped
 * defensively rather than letting `series.setData` throw.
 */
function toChartData(points: HistoryPoint[]): LineData<UTCTimestamp>[] {
  const data: LineData<UTCTimestamp>[] = [];
  let lastTime = -Infinity;
  for (const point of points) {
    if (point.t <= lastTime) continue;
    data.push({ time: point.t as UTCTimestamp, value: point.price });
    lastTime = point.t;
  }
  return data;
}

export default function PriceChart({ ticker, points }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  // Create the chart once on mount; dispose it on unmount.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#2a2a3a' },
        horzLines: { color: '#2a2a3a' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        borderColor: '#2a2a3a',
      },
      rightPriceScale: {
        borderColor: '#2a2a3a',
      },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const series = chart.addSeries(LineSeries, {
      color: '#209dd7',
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Update (or clear) the series data whenever the selection or its ticks change.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    if (!ticker || points.length === 0) {
      series.setData([]);
      return;
    }

    series.setData(toChartData(points));
    chartRef.current?.timeScale().fitContent();
  }, [ticker, points]);

  const showEmptyHint = !ticker || points.length === 0;

  return (
    <div className="relative h-full w-full bg-panel">
      <div ref={containerRef} className="h-full w-full" />
      {showEmptyHint && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-gray-500">
          {ticker ? 'Waiting for price ticks…' : 'Select a ticker to view its chart'}
        </div>
      )}
    </div>
  );
}
