import { useEffect, useState } from 'react';
import { api } from '../api';
import type { OrbitalZone, FeralAiEvent } from '../api';

const THREAT_COLORS: Record<string, string> = {
  DORMANT: 'var(--eve-green)',
  ACTIVE: 'var(--eve-yellow)',
  EVOLVED: 'var(--eve-orange)',
  CRITICAL: 'var(--eve-red)',
};

function timeAgo(ts: number | null): string {
  if (!ts) return 'never';
  const delta = Math.floor(Date.now() / 1000) - ts;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  return `${Math.floor(delta / 3600)}h ago`;
}

export function OrbitalZones() {
  const [zones, setZones] = useState<OrbitalZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [history, setHistory] = useState<FeralAiEvent[]>([]);

  useEffect(() => {
    api.orbitalZones(filter || undefined)
      .then((r) => { setZones(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filter]);

  const loadHistory = (zoneId: string) => {
    if (selectedZone === zoneId) {
      setSelectedZone(null);
      return;
    }
    setSelectedZone(zoneId);
    api.zoneHistory(zoneId)
      .then((r) => setHistory(r.data))
      .catch(() => setHistory([]));
  };

  if (loading) return <div className="text-[var(--eve-dim)]">Loading zones...</div>;

  const evolved = zones.filter((z) => z.feral_ai_tier >= 2);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
          Orbital Zones
        </h3>
        {evolved.length > 0 && (
          <span className="text-xs bg-red-900/40 border border-red-900/60 rounded px-2 py-0.5 text-[var(--eve-red)] font-bold animate-pulse">
            {evolved.length} AI EVOLVED
          </span>
        )}
      </div>

      {/* Filter */}
      <div className="flex gap-1 text-xs">
        {['', 'DORMANT', 'ACTIVE', 'EVOLVED', 'CRITICAL'].map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-2 py-1 rounded border transition-colors ${
              filter === level
                ? 'border-[var(--eve-green)] text-[var(--eve-green)]'
                : 'border-[var(--eve-border)] text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
            }`}
          >
            {level || 'ALL'}
          </button>
        ))}
      </div>

      {zones.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No zones found.</div>
      )}

      {/* Zone list */}
      {zones.map((zone) => (
        <div key={zone.zone_id}>
          <div
            onClick={() => loadHistory(zone.zone_id)}
            className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3 cursor-pointer hover:border-[var(--eve-green)] transition-colors"
          >
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: THREAT_COLORS[zone.threat_level] || 'gray' }}
                />
                <span className="text-sm font-bold text-[var(--eve-text)]">
                  {zone.name || zone.zone_id}
                </span>
                <span
                  className="text-xs font-bold"
                  style={{ color: THREAT_COLORS[zone.threat_level] || 'gray' }}
                >
                  {zone.threat_level}
                </span>
              </div>
              <div className="text-xs text-[var(--eve-dim)] flex items-center gap-2">
                {zone.stale && (
                  <span className="text-[var(--eve-yellow)] font-bold">STALE</span>
                )}
                <span>Scanned {timeAgo(zone.last_scanned)}</span>
              </div>
            </div>
            <div className="text-xs text-[var(--eve-dim)] mt-1">
              Tier {zone.feral_ai_tier} &middot; {zone.solar_system_id}
            </div>
          </div>

          {/* History dropdown */}
          {selectedZone === zone.zone_id && history.length > 0 && (
            <div className="ml-4 border-l-2 border-[var(--eve-border)] pl-3 mt-1 space-y-1">
              {history.map((evt, i) => (
                <div key={i} className="text-xs text-[var(--eve-dim)]">
                  <span style={{ color: THREAT_COLORS[evt.new_threat] }}>
                    {evt.old_threat} &rarr; {evt.new_threat}
                  </span>
                  <span className="ml-2">
                    {new Date(evt.timestamp * 1000).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
