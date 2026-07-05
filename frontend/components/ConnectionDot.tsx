'use client';

/**
 * ConnectionDot — a small colored dot + label reflecting SSE connection
 * health, driven by `useLivePrices().status`.
 *
 * Mapping: 'connected' -> green (up token), 'connecting' | 'reconnecting'
 * -> yellow (accent token). There is no explicit 'disconnected' value in
 * `ConnectionStatus` today (EventSource auto-retries forever), but the
 * component accepts any string so a future 'disconnected' state renders
 * red without a code change here.
 */

import type { ConnectionStatus } from '../lib/types';

export interface ConnectionDotProps {
  status: ConnectionStatus;
}

interface DotVisual {
  colorClass: string;
  label: string;
}

function visualFor(status: ConnectionStatus): DotVisual {
  switch (status) {
    case 'connected':
      return { colorClass: 'bg-up', label: 'Connected' };
    case 'connecting':
    case 'reconnecting':
      return { colorClass: 'bg-accent', label: 'Reconnecting' };
    default:
      return { colorClass: 'bg-down', label: 'Disconnected' };
  }
}

export default function ConnectionDot({ status }: ConnectionDotProps) {
  const { colorClass, label } = visualFor(status);

  return (
    <div className="flex items-center gap-2" role="status" aria-label={`Connection status: ${label}`}>
      <span
        className={`h-2.5 w-2.5 rounded-full ${colorClass}`}
        title={label}
        aria-hidden="true"
      />
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  );
}
