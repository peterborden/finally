'use client';

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Panel } from './Panel';
import { fmtMoney } from '@/lib/format';
import type { Snapshot } from '@/lib/types';

interface PnLChartProps {
  snapshots: Snapshot[];
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

export function PnLChart({ snapshots }: PnLChartProps) {
  const data = snapshots.map((s) => ({ t: s.recorded_at, value: s.total_value }));
  const first = data[0]?.value ?? 0;
  const last = data[data.length - 1]?.value ?? 0;
  const stroke = last >= first ? '#3fb950' : '#f85149';

  return (
    <Panel title="Portfolio Value" bodyClassName="p-2">
      {data.length < 2 ? (
        <div className="flex h-full items-center justify-center text-xs text-flat" data-testid="pnl-empty">
          Recording portfolio value…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
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
              width={56}
              orientation="right"
              tickFormatter={(v) => fmtMoney(v)}
            />
            <Tooltip
              contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 6, fontSize: 12 }}
              labelFormatter={(t) => fmtTime(t as string)}
              formatter={(v: number) => [fmtMoney(v), 'Value']}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
