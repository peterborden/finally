/**
 * Minimal SSE reader for tests. Opens GET {baseURL}/api/stream/prices, reads the
 * stream for up to `windowMs`, and returns the parsed `data:` payloads of each
 * received event. Uses Node's global fetch + AbortController (available in Node 18+).
 */
export interface SsePriceEntry {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number | string;
  change: number;
  change_percent: number;
  direction: 'up' | 'down' | 'flat';
}

export type SsePayload = Record<string, SsePriceEntry>;

export async function collectSseEvents(
  baseURL: string,
  opts: { windowMs?: number; maxEvents?: number } = {},
): Promise<SsePayload[]> {
  const windowMs = opts.windowMs ?? 4000;
  const maxEvents = opts.maxEvents ?? 50;
  const url = `${baseURL.replace(/\/$/, '')}/api/stream/prices`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), windowMs);
  const events: SsePayload[] = [];

  try {
    const res = await fetch(url, {
      headers: { Accept: 'text/event-stream' },
      signal: controller.signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`SSE connect failed: ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (events.length < maxEvents) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE events are separated by a blank line.
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop() ?? '';
      for (const chunk of chunks) {
        const dataLines = chunk
          .split('\n')
          .filter((l) => l.startsWith('data:'))
          .map((l) => l.slice(5).trim());
        if (dataLines.length === 0) continue;
        const raw = dataLines.join('\n');
        try {
          events.push(JSON.parse(raw));
        } catch {
          // keepalive / comment / non-JSON heartbeat — ignore
        }
      }
    }
  } catch (err) {
    if (!(err instanceof Error && err.name === 'AbortError')) throw err;
  } finally {
    clearTimeout(timer);
  }
  return events;
}
