import { useEffect, useState } from 'react';
import { api } from '../api';
import type { CycleInfo } from '../api';

export function CycleBanner() {
  const [cycle, setCycle] = useState<CycleInfo | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.cycle()
      .then((r) => setCycle(r.data))
      .catch(() => setError(true));
  }, []);

  if (!cycle && !error) return null;

  if (!cycle && error) {
    return (
      <div className="bg-[var(--eve-surface)] border-b border-[var(--eve-border)] px-4 py-1.5 text-center">
        <span className="text-xs font-bold tracking-widest text-[var(--eve-orange)]">
          CYCLE 5
        </span>
        <span className="text-xs text-[var(--eve-dim)] mx-2">//</span>
        <span className="text-xs font-bold tracking-wider text-[var(--eve-text)]">
          SHROUD OF FEAR
        </span>
      </div>
    );
  }

  return (
    <div className="bg-[var(--eve-surface)] border-b border-[var(--eve-border)] px-4 py-1.5 text-center">
      <span className="text-xs font-bold tracking-widest text-[var(--eve-orange)]">
        CYCLE {cycle!.number}
      </span>
      <span className="text-xs text-[var(--eve-dim)] mx-2">//</span>
      <span className="text-xs font-bold tracking-wider text-[var(--eve-text)]">
        {cycle!.name.toUpperCase()}
      </span>
      <span className="text-xs text-[var(--eve-dim)] mx-2">//</span>
      <span className="text-xs text-[var(--eve-green)]">
        DAY {cycle!.days_elapsed}
      </span>
    </div>
  );
}
