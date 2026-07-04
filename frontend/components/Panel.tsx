import type { ReactNode } from 'react';

interface PanelProps {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
  titleTestId?: string;
}

/** A titled terminal panel with a header strip and a scroll-managed body. */
export function Panel({ title, right, children, className = '', bodyClassName = '', testId, titleTestId }: PanelProps) {
  return (
    <section
      data-testid={testId}
      className={`flex min-h-0 flex-col overflow-hidden rounded-md border border-border-subtle bg-bg-panel ${className}`}
    >
      {title && (
        <header className="flex shrink-0 items-center justify-between border-b border-border-subtle px-3 py-1.5">
          <h2 data-testid={titleTestId} className="text-[11px] font-semibold uppercase tracking-wider text-flat">{title}</h2>
          {right}
        </header>
      )}
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
