import { useEffect, useState } from 'react';
import { api } from '../api';
import type { HotzoneData } from '../api';

function dangerStyle(level: string): { color: string; bg: string } {
  switch (level) {
    case 'extreme': return { color: 'var(--eve-red)', bg: 'rgba(255, 50, 50, 0.15)' };
    case 'high': return { color: 'var(--eve-orange)', bg: 'rgba(255, 150, 50, 0.1)' };
    case 'moderate': return { color: '#f0c040', bg: 'rgba(240, 192, 64, 0.08)' };
    case 'low': return { color: 'var(--eve-green)', bg: 'rgba(0, 255, 136, 0.05)' };
    default: return { color: 'var(--eve-dim)', bg: 'transparent' };
  }
}

function timeAgo(ts: number): string {
  const delta = Math.floor(Date.now() / 1000) - ts;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

export function HotzoneMap() {
  const [hotzones, setHotzones] = useState<HotzoneData[]>([]);
  const [window, setWindow] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.hotzones(window).then((d) => setHotzones(d.hotzones)).catch(() => setHotzones([])).finally(() => setLoading(false));
  }, [window]);

  const windows = ['24h', '7d', '30d', 'all'] as const;

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
          Danger Zones
        </h3>
        <div className="flex gap-1">
          {windows.map((w) => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-2 py-0.5 text-xs rounded ${
                window === w
                  ? 'bg-[var(--eve-green)] text-[var(--eve-bg)] font-bold'
                  : 'text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
              }`}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-[var(--eve-dim)] text-sm">Scanning systems...</div>}

      {!loading && hotzones.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No kill activity in this window.</div>
      )}

      {!loading && hotzones.length > 0 && (
        <div className="space-y-1.5">
          {hotzones.map((hz) => {
            const style = dangerStyle(hz.danger_level);
            return (
              <div
                key={hz.solar_system_id}
                className="border border-[var(--eve-border)] rounded px-3 py-2"
                style={{ backgroundColor: style.bg }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-sm font-bold" style={{ color: style.color }}>
                      {hz.solar_system_name || hz.solar_system_id.slice(0, 12)}
                    </span>
                    <span className="text-xs text-[var(--eve-dim)] ml-2 uppercase">
                      {hz.danger_level}
                    </span>
                  </div>
                  <span className="text-xs text-[var(--eve-dim)]">
                    {timeAgo(hz.latest_kill)}
                  </span>
                </div>
                <div className="flex gap-4 mt-1 text-xs text-[var(--eve-dim)]">
                  <span><span style={{ color: style.color }}>{hz.kills}</span> kills</span>
                  <span>{hz.unique_attackers} attackers</span>
                  <span>{hz.unique_victims} victims</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
