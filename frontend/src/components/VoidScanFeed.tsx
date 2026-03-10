import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ScanResult } from '../api';

const RESULT_COLORS: Record<string, string> = {
  CLEAR: 'var(--eve-green)',
  ANOMALY: 'var(--eve-yellow)',
  HOSTILE: 'var(--eve-red)',
  UNKNOWN: 'var(--eve-dim)',
};

function timeAgo(ts: number): string {
  const delta = Math.floor(Date.now() / 1000) - ts;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  return `${Math.floor(delta / 3600)}h ago`;
}

export function VoidScanFeed() {
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(false);
    const load = (isInitial: boolean) => {
      api.scanFeed(20)
        .then((r) => {
          setScans(r.data);
          setLoading(false);
        })
        .catch(() => {
          if (isInitial) setError(true);
          setLoading(false);
        });
    };
    load(true);
    const interval = setInterval(() => load(false), 30000);
    return () => clearInterval(interval);
  }, [retryKey]);

  if (loading) return <div className="text-[var(--eve-dim)]">Loading scans...</div>;

  if (error) {
    return (
      <div className="text-xs text-[var(--eve-red)]">
        Failed to load scan feed.{' '}
        <button
          onClick={() => { setError(false); setRetryKey((k) => k + 1); }}
          className="underline hover:text-[var(--eve-text)] transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const hostileZones = new Set(
    scans.filter((s) => s.zone_hostile_recent).map((s) => s.zone_id)
  );

  return (
    <div className="space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Void Scan Feed
      </h3>

      {hostileZones.size > 0 && (
        <div className="bg-red-900/20 border border-red-900/40 rounded px-3 py-2 text-xs text-[var(--eve-red)] font-bold">
          SCAN BEFORE YOU MOVE &mdash; {hostileZones.size} zone(s) with recent hostile activity
        </div>
      )}

      {scans.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No scan data yet.</div>
      )}

      <div className="space-y-1 max-h-80 overflow-y-auto">
        {scans.map((scan) => (
          <div
            key={scan.scan_id}
            className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-3 py-2 flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-bold px-1.5 py-0.5 rounded"
                style={{
                  color: RESULT_COLORS[scan.result_type] || 'gray',
                  backgroundColor: scan.result_type === 'HOSTILE' ? 'rgba(255,0,0,0.15)' : 'transparent',
                  border: `1px solid ${RESULT_COLORS[scan.result_type] || 'gray'}`,
                }}
              >
                {scan.result_type}
              </span>
              <span className="text-xs text-[var(--eve-text)]">
                {scan.zone_id}
              </span>
              {scan.scanner_name && (
                <span className="text-xs text-[var(--eve-dim)]">
                  by {scan.scanner_name}
                </span>
              )}
            </div>
            <span className="text-xs text-[var(--eve-dim)]">
              {timeAgo(scan.scanned_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
