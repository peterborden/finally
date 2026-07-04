import type { ConnectionStatus } from '@/lib/types';

const MAP: Record<ConnectionStatus, { color: string; label: string; pulse: boolean }> = {
  connected: { color: 'bg-up', label: 'Live', pulse: false },
  reconnecting: { color: 'bg-accent', label: 'Reconnecting', pulse: true },
  disconnected: { color: 'bg-down', label: 'Disconnected', pulse: false },
};

export function ConnectionDot({ status }: { status: ConnectionStatus }) {
  const { color, label, pulse } = MAP[status];
  return (
    <div className="flex items-center gap-1.5" title={`Stream: ${label}`} data-testid="connection-status" data-state={status}>
      <span className={`relative flex h-2.5 w-2.5`}>
        {pulse && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${color}`} />}
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
      </span>
      <span className="text-[11px] text-flat">{label}</span>
    </div>
  );
}
