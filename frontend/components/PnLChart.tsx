'use client';

/**
 * PnLChart — a lightweight-charts line series plotting total portfolio
 * value over time from `Snapshot[]` (GET /api/portfolio/history).
 *
 * lightweight-charts v5 requires `chart.addSeries(LineSeries, options)`
 * (the v4 `addLineSeries` method was removed) and strictly ascending,
 * unique series times. `recorded_at` is an ISO-8601 UTC string; it is
 * parsed to whole seconds and any collisions (two snapshots landing in the
 * same second) are nudged forward by one second so the series stays
 * strictly increasing without dropping data points.
 */

import { useEffect, useRef } from 'react';
import {
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { Snapshot } from '../lib/types';

interface PnLChartProps {
  history: Snapshot[];
}

interface PnLPoint {
  time: UTCTimestamp;
  value: number;
}

/** Convert snapshots into strictly ascending, unique-time series points. */
function toSeriesData(history: Snapshot[]): PnLPoint[] {
  const sorted = [...history].sort(
    (a, b) => Date.parse(a.recorded_at) - Date.parse(b.recorded_at),
  );

  const points: PnLPoint[] = [];
  let lastTime = Number.NEGATIVE_INFINITY;

  for (const snapshot of sorted) {
    const parsed = Math.floor(Date.parse(snapshot.recorded_at) / 1000);
    if (Number.isNaN(parsed)) {
      continue;
    }
    const time = parsed <= lastTime ? lastTime + 1 : parsed;
    lastTime = time;
    points.push({ time: time as UTCTimestamp, value: snapshot.total_value });
  }

  return points;
}

export function PnLChart({ history }: PnLChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#1a1a2e' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#2a2a3a' },
        horzLines: { color: '#2a2a3a' },
      },
      rightPriceScale: { borderColor: '#2a2a3a' },
      timeScale: { borderColor: '#2a2a3a', timeVisible: true },
      width: container.clientWidth,
      height: container.clientHeight || 200,
    });

    const series = chart.addSeries(LineSeries, {
      color: '#209dd7',
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (!containerRef.current) {
        return;
      }
      chart.resize(containerRef.current.clientWidth, containerRef.current.clientHeight || 200);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) {
      return;
    }
    seriesRef.current.setData(toSeriesData(history));
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  const isEmpty = history.length === 0;

  return (
    <div className="relative h-full min-h-[160px] w-full rounded border border-border-muted bg-panel p-2">
      <div ref={containerRef} className="h-full w-full" />
      {isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">
          No portfolio history yet
        </div>
      )}
    </div>
  );
}
