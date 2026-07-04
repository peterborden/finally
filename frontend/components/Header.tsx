'use client';

import { ConnectionDot } from './ConnectionDot';
import { fmtMoney, fmtSignedMoney, fmtPercent, pnlColor } from '@/lib/format';
import type { ConnectionStatus, Portfolio } from '@/lib/types';

interface HeaderProps {
  portfolio: Portfolio | null;
  status: ConnectionStatus;
}

function Stat({
  label,
  value,
  valueClass = '',
  testId,
}: {
  label: string;
  value: string;
  valueClass?: string;
  testId?: string;
}) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="text-[10px] uppercase tracking-wider text-flat">{label}</span>
      <span data-testid={testId} className={`tabular-nums text-sm font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

export function Header({ portfolio, status }: HeaderProps) {
  const pnl = portfolio?.total_unrealized_pnl ?? null;
  const totalValue = portfolio?.total_value ?? null;
  const cash = portfolio?.cash_balance ?? null;
  // Percentage of unrealized P&L relative to invested basis.
  const basis = portfolio ? portfolio.positions_value - (portfolio.total_unrealized_pnl ?? 0) : 0;
  const pnlPct = basis > 0 && pnl != null ? (pnl / basis) * 100 : null;

  return (
    <header data-testid="header" className="flex shrink-0 items-center justify-between border-b border-border-subtle bg-bg-panel px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold tracking-tight">
          <span className="text-accent">Fin</span>
          <span className="text-brand">Ally</span>
        </span>
        <span className="hidden text-[10px] uppercase tracking-widest text-flat sm:inline">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <Stat label="Portfolio Value" value={fmtMoney(totalValue)} valueClass="text-gray-100" testId="portfolio-total-value" />
        <Stat
          label="Unrealized P&L"
          value={pnl == null ? '—' : `${fmtSignedMoney(pnl)} (${fmtPercent(pnlPct)})`}
          valueClass={pnlColor(pnl)}
        />
        <Stat label="Cash" value={fmtMoney(cash)} valueClass="text-accent" testId="cash-balance" />
        <ConnectionDot status={status} />
      </div>
    </header>
  );
}
