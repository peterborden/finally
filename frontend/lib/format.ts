// Display formatting helpers. All tolerate null/undefined by rendering an em dash.

const DASH = '—';

export function fmtPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function fmtMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return `$${fmtPrice(value)}`;
}

/** Signed money, e.g. +$25.00 / -$12.30. */
export function fmtSignedMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  return `${sign}$${fmtPrice(Math.abs(value))}`;
}

export function fmtPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function fmtQty(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  // Show up to 4 decimals for fractional shares, trimming trailing zeros.
  return Number(value.toFixed(4)).toString();
}

/** Tailwind text color class for a signed value. */
export function pnlColor(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value) || value === 0) return 'text-flat';
  return value > 0 ? 'text-up' : 'text-down';
}

export function directionColor(direction: string | null | undefined): string {
  if (direction === 'up') return 'text-up';
  if (direction === 'down') return 'text-down';
  return 'text-flat';
}
