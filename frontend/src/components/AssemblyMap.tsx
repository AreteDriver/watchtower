import { useEffect, useState } from 'react';
import { api } from '../api';
import type { AssemblyStats } from '../api';

const TYPE_NAMES: Record<string, string> = {
  '88063': 'Refinery',
  '88064': 'Heavy Refinery',
  '88067': 'Printer',
  '88068': 'Assembler',
  '88069': 'Mini Berth',
  '88070': 'Berth',
  '88071': 'Heavy Berth',
  '87119': 'Mini Printer',
  '87120': 'Heavy Printer',
  '88093': 'Shelter',
  '88094': 'Heavy Shelter',
  '90184': 'Relay',
  '91871': 'Nest',
  '91978': 'Nursery',
};

const STATE_COLORS: Record<string, string> = {
  online: 'var(--eve-green)',
  anchored: 'var(--eve-blue)',
  offline: 'var(--eve-red)',
  unanchored: 'var(--eve-dim)',
};

export function AssemblyMap() {
  const [stats, setStats] = useState<AssemblyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.assemblies().then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
        <span className="text-[var(--eve-dim)] text-sm">Loading assembly network...</span>
      </div>
    );
  }

  if (!stats || stats.total === 0) {
    return (
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
        <h3 className="text-sm font-bold text-[var(--eve-dim)] uppercase tracking-wider mb-2">
          Watcher Network
        </h3>
        <p className="text-xs text-[var(--eve-dim)]">No assemblies deployed yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-[var(--eve-dim)] uppercase tracking-wider">
          Watcher Network
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[var(--eve-green)] text-sm font-bold">{stats.online}</span>
          <span className="text-xs text-[var(--eve-dim)]">/ {stats.total} online</span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2">
        <div className="text-center">
          <div className="text-base font-bold text-[var(--eve-green)]">{stats.systems_covered}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Systems</div>
        </div>
        <div className="text-center">
          <div className="text-base font-bold text-[var(--eve-text)]">{stats.online}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Online</div>
        </div>
        <div className="text-center">
          <div className="text-base font-bold text-[var(--eve-red)]">{stats.offline}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Offline</div>
        </div>
      </div>

      {/* Assembly list */}
      <div className="max-h-40 overflow-y-auto">
        {stats.assemblies.map((a) => (
          <div key={a.assembly_id} className="flex items-center justify-between text-xs py-0.5 border-b border-[var(--eve-border)]/50">
            <div className="flex items-center gap-1.5">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: STATE_COLORS[a.state] || 'var(--eve-dim)' }}
              />
              <span className="text-[var(--eve-text)]">
                {TYPE_NAMES[a.type] || a.type}
              </span>
            </div>
            <span className="text-[var(--eve-dim)] font-mono text-[10px]">
              {a.solar_system_name || a.solar_system_id?.slice(0, 8) || a.assembly_id?.slice(0, 10)}
            </span>
          </div>
        ))}
      </div>

      <div className="text-[10px] text-[var(--eve-dim)] opacity-60">
        Auto-updated from chain data
      </div>
    </div>
  );
}
