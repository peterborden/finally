'use client';

import { useEffect, useRef, useState } from 'react';

export interface FlashState {
  dir: 'up' | 'down' | null;
  /** Increments on every price change so callers can remount to restart the CSS animation. */
  seq: number;
}

/**
 * Tracks price changes and returns a flash direction + sequence number.
 * Consumers apply `animate-flash-up` / `animate-flash-down` keyed by `seq` so the
 * ~500ms fade restarts cleanly on each successive tick.
 */
export function usePriceFlash(price: number | null | undefined): FlashState {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<FlashState>({ dir: null, seq: 0 });

  useEffect(() => {
    if (price == null || Number.isNaN(price)) return;
    const last = prev.current;
    if (last != null && price !== last) {
      setFlash((f) => ({ dir: price > last ? 'up' : 'down', seq: f.seq + 1 }));
    }
    prev.current = price;
  }, [price]);

  return flash;
}

export function flashClass(flash: FlashState): string {
  if (flash.dir === 'up') return 'animate-flash-up';
  if (flash.dir === 'down') return 'animate-flash-down';
  return '';
}
