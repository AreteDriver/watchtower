import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Clone } from '../api';

const CLONE_RESERVE_THRESHOLD = 5;

function formatEta(manufacturedAt: number, timeSec: number | undefined): string {
  if (!timeSec) return 'unknown';
  const eta = manufacturedAt + timeSec;
  const remaining = eta - Math.floor(Date.now() / 1000);
  if (remaining <= 0) return 'ready';
  if (remaining < 60) return `${remaining}s`;
  if (remaining < 3600) return `${Math.floor(remaining / 60)}m`;
  return `${Math.floor(remaining / 3600)}h ${Math.floor((remaining % 3600) / 60)}m`;
}

export function CloneStatus() {
  const [clones, setClones] = useState<Clone[]>([]);
  const [queue, setQueue] = useState<Clone[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.clones(), api.cloneQueue()])
      .then(([c, q]) => {
        setClones(c.data);
        setQueue(q.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-[var(--eve-dim)]">Loading clones...</div>;

  const lowReserve = clones.length < CLONE_RESERVE_THRESHOLD;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
          Clone Status
        </h3>
        <span className="text-xs text-[var(--eve-dim)]">
          {clones.length} active
        </span>
      </div>

      {lowReserve && (
        <div className="bg-orange-900/20 border border-orange-900/40 rounded px-3 py-2 text-xs text-[var(--eve-orange)] font-bold">
          LOW CLONE RESERVE &mdash; {clones.length} active clones (threshold: {CLONE_RESERVE_THRESHOLD})
        </div>
      )}

      {/* Active clones */}
      {clones.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3">
          <div className="text-xs text-[var(--eve-dim)] mb-2 uppercase font-bold">Active</div>
          <div className="space-y-1">
            {clones.slice(0, 10).map((c) => (
              <div key={c.clone_id} className="flex justify-between text-xs">
                <span className="text-[var(--eve-text)]">{c.owner_name || c.owner_id}</span>
                <span className="text-[var(--eve-dim)]">{c.blueprint_id}</span>
              </div>
            ))}
            {clones.length > 10 && (
              <div className="text-xs text-[var(--eve-dim)]">+{clones.length - 10} more</div>
            )}
          </div>
        </div>
      )}

      {/* Manufacturing queue */}
      {queue.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3">
          <div className="text-xs text-[var(--eve-dim)] mb-2 uppercase font-bold">Manufacturing Queue</div>
          <div className="space-y-1">
            {queue.map((c) => (
              <div key={c.clone_id} className="flex justify-between text-xs">
                <div>
                  <span className="text-[var(--eve-text)]">{c.blueprint_name || 'Unknown'}</span>
                  {c.tier && <span className="text-[var(--eve-dim)] ml-1">T{c.tier}</span>}
                </div>
                <span className="text-[var(--eve-green)]">
                  ETA: {formatEta(c.manufactured_at, c.manufacture_time_sec)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {clones.length === 0 && queue.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No clone data yet.</div>
      )}
    </div>
  );
}
