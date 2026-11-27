import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePriceStream } from '@/lib/usePriceStream';
import type { PriceMap } from '@/lib/types';

// Minimal EventSource double we can drive from tests.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;

  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  emit(data: PriceMap) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
  emitRaw(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }
  fail(closed: boolean) {
    this.readyState = closed ? 2 : 0;
    this.onerror?.();
  }
  close() {
    this.readyState = 2;
  }
}

describe('usePriceStream', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('connects and ingests price updates into prices + sparklines', async () => {
    const { result } = renderHook(() => usePriceStream());
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe('/api/stream/prices');
    expect(result.current.status).toBe('reconnecting');

    act(() => es.open());
    await waitFor(() => expect(result.current.status).toBe('connected'));

    const frame: PriceMap = {
      AAPL: { ticker: 'AAPL', price: 192.5, previous_price: 191, change: 1.5, change_percent: 0.78, direction: 'up', timestamp: 1000 },
    };
    act(() => es.emit(frame));
    await waitFor(() => expect(result.current.prices.AAPL?.price).toBe(192.5));

    // A second tick accumulates a sparkline series.
    act(() => es.emit({ AAPL: { ...frame.AAPL, price: 193.0, timestamp: 2000 } }));
    await waitFor(() => expect(result.current.sparklines.AAPL?.length).toBe(2));
    expect(result.current.sparklines.AAPL.map((p) => p.price)).toEqual([192.5, 193.0]);
  });

  it('ignores malformed frames without crashing', async () => {
    const { result } = renderHook(() => usePriceStream());
    const es = FakeEventSource.instances[0];
    act(() => es.open());
    act(() => es.emitRaw('not json{'));
    expect(result.current.prices).toEqual({});
  });

  it('reports reconnecting on a transient error and disconnected when closed', async () => {
    const { result } = renderHook(() => usePriceStream());
    const es = FakeEventSource.instances[0];
    act(() => es.fail(false));
    await waitFor(() => expect(result.current.status).toBe('reconnecting'));
    act(() => es.fail(true));
    await waitFor(() => expect(result.current.status).toBe('disconnected'));
  });
});
