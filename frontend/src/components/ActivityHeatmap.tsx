import { useEffect, useState } from 'react';
import { api } from '../api';

interface Props {
  entityId: string;
}

export function ActivityHeatmap({ entityId }: Props) {
  const [hours, setHours] = useState<number[]>(new Array(24).fill(0));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const now = Math.floor(Date.now() / 1000);
    api.timeline(entityId, now - 14 * 86400, now).then((data) => {
      const counts = new Array(24).fill(0);
      data.events.forEach((e) => {
        const hour = Math.floor((e.timestamp % 86400) / 3600);
        counts[hour]++;
      });
      setHours(counts);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [entityId]);

  if (loading) return <div className="text-[var(--eve-dim)] text-xs">Loading activity...</div>;

  const max = Math.max(...hours, 1);

  return (
    <div className="space-y-2">
      <h4 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Activity by Hour (UTC)
      </h4>
      <div className="flex items-end gap-px h-16">
        {hours.map((count, hour) => {
          const pct = (count / max) * 100;
          const isActive = count > 0;
          return (
            <div key={hour} className="flex-1 flex flex-col items-center group relative">
              <div
                className="w-full rounded-t transition-all"
                style={{
                  height: `${Math.max(pct, 2)}%`,
                  backgroundColor: isActive ? 'var(--eve-green)' : 'var(--eve-border)',
                  opacity: isActive ? Math.max(0.3, pct / 100) : 0.2,
                }}
              />
              <div className="absolute bottom-full mb-1 hidden group-hover:block bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-1.5 py-0.5 text-xs whitespace-nowrap z-10">
                {hour}:00 — {count} events
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-[var(--eve-dim)]">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:00</span>
      </div>
    </div>
  );
}
