import { useState } from 'react';
import { useIsMobile } from '../hooks/useIsMobile';

interface Props {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function CollapsibleSection({ title, defaultOpen = true, children }: Props) {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(defaultOpen);

  if (!isMobile) return <>{children}</>;

  return (
    <div className="border border-[var(--eve-border)] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3
                   bg-[var(--eve-surface)] text-xs font-bold uppercase tracking-wider
                   text-[var(--eve-dim)] hover:text-[var(--eve-text)] transition-colors"
      >
        {title}
        <span className="text-[var(--eve-dim)]">{open ? '\u25B2' : '\u25BC'}</span>
      </button>
      {open && <div className="p-1">{children}</div>}
    </div>
  );
}
