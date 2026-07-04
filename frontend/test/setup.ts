import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

// Recharts' ResponsiveContainer relies on ResizeObserver, absent in jsdom.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver =
  globalThis.ResizeObserver ?? (ResizeObserverStub as unknown as typeof ResizeObserver);

// Give ResponsiveContainer a non-zero measured size so charts render in tests.
Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 300 });

// jsdom lacks scrollTo.
Element.prototype.scrollTo = Element.prototype.scrollTo ?? (() => {});

// Silence noisy Recharts width/height warnings in test output.
vi.spyOn(console, 'warn').mockImplementation(() => {});
