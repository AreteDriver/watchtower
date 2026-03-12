import { useState, useEffect } from 'react';
import { api } from '../api';
import type { AnalyticsData } from '../api';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
      <div className="text-xs text-[var(--eve-dim)] uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold text-[var(--eve-green)] mt-1">{typeof value === 'number' ? value.toLocaleString() : value}</div>
      {sub && <div className="text-xs text-[var(--eve-dim)] mt-1">{sub}</div>}
    </div>
  );
}

export function AdminAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics()
      .then(setData)
      .catch(() => setError('Failed to load analytics'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-8 text-[var(--eve-dim)]">
        <span className="pulse-green text-[var(--eve-green)]">///</span> Loading analytics...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-[var(--eve-red)] bg-red-900/20 border border-red-900/40 rounded px-4 py-3">
        {error || 'No data'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-[var(--eve-green)] tracking-wider">
          ADMIN ANALYTICS
        </h2>
        <div className="text-xs text-[var(--eve-dim)]">
          Last updated: {new Date(data.timestamp * 1000).toLocaleString()}
        </div>
      </div>

      {/* Totals */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Platform Totals</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Entities" value={data.totals.entities} sub={`${data.totals.characters} chars / ${data.totals.gates} gates`} />
          <StatCard label="Killmails" value={data.totals.killmails} />
          <StatCard label="Gate Events" value={data.totals.gate_events} />
          <StatCard label="Titles Earned" value={data.totals.titles} />
          <StatCard label="Stories Generated" value={data.totals.stories} />
          <StatCard label="Active Watches" value={data.totals.active_watches} />
        </div>
      </div>

      {/* Activity */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Activity</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <StatCard label="Kills (24h)" value={data.activity.kills_24h} sub={`${data.activity.kills_7d} this week`} />
          <StatCard label="Gate Transits (24h)" value={data.activity.gate_transits_24h} sub={`${data.activity.gate_transits_7d} this week`} />
          <StatCard label="New Entities (24h)" value={data.activity.new_entities_24h} />
        </div>
      </div>

      {/* Subscriptions */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Subscriptions</h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Scout" value={data.subscriptions.scout} />
          <StatCard label="Oracle" value={data.subscriptions.oracle} />
          <StatCard label="Spymaster" value={data.subscriptions.spymaster} />
        </div>
      </div>

      {/* Top Active (7d) */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Top Active (7d)</h3>
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--eve-border)] text-[var(--eve-dim)] text-xs uppercase">
                <th className="px-4 py-2 text-left">Entity</th>
                <th className="px-4 py-2 text-right">Events</th>
                <th className="px-4 py-2 text-right">Kills</th>
                <th className="px-4 py-2 text-right">Deaths</th>
              </tr>
            </thead>
            <tbody>
              {data.top_active_7d.map((e) => (
                <tr key={e.entity_id} className="border-b border-[var(--eve-border)] last:border-0 hover:bg-[var(--eve-border)]">
                  <td className="px-4 py-2 text-[var(--eve-green)] font-mono text-xs">
                    {e.display_name || e.entity_id.slice(0, 12)}
                  </td>
                  <td className="px-4 py-2 text-right text-[var(--eve-text)]">{e.event_count.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-[var(--eve-red)]">{e.kill_count}</td>
                  <td className="px-4 py-2 text-right text-[var(--eve-dim)]">{e.death_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
