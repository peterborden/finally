'use client';

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Panel } from './Panel';
import { fmtPrice, fmtPercent, directionColor } from '@/lib/format';
import type { Quote, SparkPoint } from '@/lib/types';

interface MainChartProps {
  ticker: string | null;
  quote: Quote | undefined;
  series: SparkPoint[];
}

function fmtTime(t: number): string {
  return new Date(t).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function MainChart({ ticker, quote, series }: MainChartProps) {
  const rising = (quote?.direction ?? 'flat') !== 'down';
  const stroke = quote?.direction === 'down' ? '#f85149' : quote?.direction === 'up' ? '#3fb950' : '#209dd7';
  const data = series.map((p) => ({ t: p.t, price: p.price }));

  return (
    <Panel
      title={ticker ? `${ticker} · Live` : 'Chart'}
      right={
        quote ? (
          <div className="flex items-center gap-3 tabular-nums">
            <span className="text-sm font-semibold text-gray-100">{fmtPrice(quote.price)}</span>
            <span className={`text-xs ${directionColor(quote.direction)}`}>{fmtPercent(quote.change_percent)}</span>
          </div>
        ) : null
      }
      bodyClassName="p-2"
    >
      {!ticker ? (
        <div className="flex h-full items-center justify-center text-xs text-flat">
          Select a ticker from the watchlist.
        </div>
      ) : data.length < 2 ? (
        <div className="flex h-full items-center justify-center text-xs text-flat" data-testid="chart-accumulating">
          Accumulating live data for {ticker}…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="mainFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="t"
              tickFormatter={fmtTime}
              tick={{ fill: '#8b949e', fontSize: 10 }}
              stroke="#30363d"
              minTickGap={48}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fill: '#8b949e', fontSize: 10 }}
              stroke="#30363d"
              width={52}
              tickFormatter={(v) => fmtPrice(v)}
              orientation="right"
            />
            <Tooltip
              contentStyle={{
                background: '#161b22',
                border: '1px solid #30363d',
                borderRadius: 6,
                fontSize: 12,
              }}
              labelFormatter={(t) => fmtTime(t as number)}
              formatter={(v: number) => [fmtPrice(v), 'Price']}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={stroke}
              strokeWidth={1.5}
              fill="url(#mainFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
