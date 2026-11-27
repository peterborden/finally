import { describe, it, expect } from 'vitest';
import {
  fmtPrice,
  fmtMoney,
  fmtSignedMoney,
  fmtPercent,
  fmtQty,
  pnlColor,
  directionColor,
} from '@/lib/format';

describe('format helpers', () => {
  it('renders an em dash for null/undefined/NaN', () => {
    expect(fmtPrice(null)).toBe('—');
    expect(fmtMoney(undefined)).toBe('—');
    expect(fmtPercent(NaN)).toBe('—');
    expect(fmtQty(null)).toBe('—');
    expect(fmtSignedMoney(null)).toBe('—');
  });

  it('formats prices and money with two decimals', () => {
    expect(fmtPrice(192.5)).toBe('192.50');
    expect(fmtMoney(1925)).toBe('$1,925.00');
  });

  it('signs money and percentages', () => {
    expect(fmtSignedMoney(25)).toBe('+$25.00');
    expect(fmtSignedMoney(-12.3)).toBe('-$12.30');
    expect(fmtPercent(1.324)).toBe('+1.32%');
    expect(fmtPercent(-0.78)).toBe('-0.78%');
  });

  it('trims fractional share quantities', () => {
    expect(fmtQty(10)).toBe('10');
    expect(fmtQty(1.5)).toBe('1.5');
    expect(fmtQty(0.1)).toBe('0.1');
  });

  it('maps signed values to semantic colors', () => {
    expect(pnlColor(5)).toBe('text-up');
    expect(pnlColor(-5)).toBe('text-down');
    expect(pnlColor(0)).toBe('text-flat');
    expect(directionColor('up')).toBe('text-up');
    expect(directionColor('down')).toBe('text-down');
    expect(directionColor('flat')).toBe('text-flat');
  });
});
