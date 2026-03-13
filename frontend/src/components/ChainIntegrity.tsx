import { useEffect, useState } from 'react';

const MONOLITH_API = 'https://monolith-evefrontier.fly.dev/api';

interface MonolithHealth {
  status: string;
  uptime_seconds: number;
  row_counts: {
    chain_events: number;
    anomalies: number;
    bug_reports: number;
    objects: number;
  };
}

interface MonolithStats {
  anomaly_rate_24h: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  events_processed_24h: number;
  false_positive_rate: number;
}

export function ChainIntegrity() {
  const [health, setHealth] = useState<MonolithHealth | null>(null);
  const [stats, setStats] = useState<MonolithStats | null>(null);
  const [status, setStatus] = useState<'loading' | 'online' | 'offline'>('loading');

  useEffect(() => {
    const load = async () => {
      try {
        const [h, s] = await Promise.all([
          fetch(`${MONOLITH_API}/health`).then((r) => r.json()),
          fetch(`${MONOLITH_API}/stats`).then((r) => r.json()),
        ]);
        setHealth(h);
        setStats(s);
        setStatus('online');
      } catch {
        setStatus('offline');
      }
    };
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  if (status === 'loading') {
    return (
      <div className="aegis-scan-container rounded-lg p-4"
        style={{ background: 'var(--eve-surface)', border: '1px solid var(--eve-border)' }}
      >
        <span className="aegis-mono text-xs text-[var(--eve-dim)]">
          CHAIN INTEGRITY MODULE LOADING...
        </span>
      </div>
    );
  }

  if (status === 'offline') {
    return (
      <div className="rounded-lg p-4"
        style={{ background: 'var(--eve-surface)', border: '1px solid var(--eve-border)' }}
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--eve-dim)]" />
          <span className="aegis-mono text-xs text-[var(--eve-dim)]">
            MONOLITH INTEGRITY MODULE — OFFLINE
          </span>
        </div>
      </div>
    );
  }

  const totalAnomalies = health?.row_counts.anomalies ?? 0;
  const eventsProcessed = health?.row_counts.chain_events ?? 0;
  const integrityRate = eventsProcessed > 0
    ? ((1 - totalAnomalies / eventsProcessed) * 100).toFixed(1)
    : '100.0';
  const criticals = stats?.by_severity?.CRITICAL ?? 0;
  const highs = stats?.by_severity?.HIGH ?? 0;

  return (
    <div className="rounded-lg p-4 space-y-3"
      style={{
        background: 'var(--eve-surface)',
        border: '1px solid var(--eve-border)',
        borderLeftWidth: '2px',
        borderLeftColor: criticals > 0 ? '#ef4444' : '#22c55e',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse" />
          <span className="aegis-mono text-xs font-bold" style={{ color: '#CCC9F8' }}>
            CHAIN INTEGRITY
          </span>
        </div>
        <span className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
          style={{ color: '#CCC9F8', borderColor: '#534AB7', background: '#26215C' }}
        >
          MONOLITH FEED
        </span>
      </div>

      {/* Integrity Score */}
      <div className="flex items-baseline gap-3">
        <span className="aegis-mono text-2xl font-bold"
          style={{ color: parseFloat(integrityRate) >= 99 ? '#22c55e' : parseFloat(integrityRate) >= 95 ? '#f59e0b' : '#ef4444' }}
        >
          {integrityRate}%
        </span>
        <span className="text-[10px] text-[var(--eve-dim)] tracking-wider font-semibold">
          CHAIN INTEGRITY RATING
        </span>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-2">
        <div className="text-center py-1.5 rounded" style={{ background: 'rgba(127, 119, 221, 0.08)' }}>
          <div className="aegis-mono text-sm font-bold text-[var(--eve-text)]">
            {eventsProcessed.toLocaleString()}
          </div>
          <div className="text-[9px] text-[var(--eve-dim)] tracking-wider">EVENTS</div>
        </div>
        <div className="text-center py-1.5 rounded" style={{ background: 'rgba(127, 119, 221, 0.08)' }}>
          <div className="aegis-mono text-sm font-bold text-[var(--eve-text)]">
            {totalAnomalies}
          </div>
          <div className="text-[9px] text-[var(--eve-dim)] tracking-wider">ANOMALIES</div>
        </div>
        <div className="text-center py-1.5 rounded" style={{ background: 'rgba(127, 119, 221, 0.08)' }}>
          <div className={`aegis-mono text-sm font-bold ${criticals > 0 ? 'text-[var(--eve-red)]' : 'text-[var(--eve-text)]'}`}>
            {criticals}
          </div>
          <div className="text-[9px] text-[var(--eve-dim)] tracking-wider">CRITICAL</div>
        </div>
        <div className="text-center py-1.5 rounded" style={{ background: 'rgba(127, 119, 221, 0.08)' }}>
          <div className={`aegis-mono text-sm font-bold ${highs > 0 ? 'text-[#f59e0b]' : 'text-[var(--eve-text)]'}`}>
            {highs}
          </div>
          <div className="text-[9px] text-[var(--eve-dim)] tracking-wider">HIGH</div>
        </div>
      </div>

      {/* Anomaly Types */}
      {stats?.by_type && Object.keys(stats.by_type).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(stats.by_type).map(([type, count]) => (
            <span key={type}
              className="aegis-mono text-[9px] tracking-wider px-1.5 py-0.5 rounded border"
              style={{ color: 'var(--eve-dim)', borderColor: 'var(--eve-border)' }}
            >
              {type.replace(/_/g, ' ')} ({count})
            </span>
          ))}
        </div>
      )}

      {/* 24h Activity */}
      {stats && (
        <div className="flex items-center justify-between text-[10px] text-[var(--eve-dim)]">
          <span>24H: {stats.anomaly_rate_24h} anomalies / {stats.events_processed_24h.toLocaleString()} events</span>
          <span>FP rate: {(stats.false_positive_rate * 100).toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}
