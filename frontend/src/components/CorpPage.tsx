import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { api } from '../api';
import type { CorpProfile } from '../api';

function threatColor(level: string): string {
  switch (level) {
    case 'extreme': return 'var(--eve-red)';
    case 'high': return 'var(--eve-orange)';
    case 'moderate': return '#f0c040';
    case 'low': return 'var(--eve-green)';
    default: return 'var(--eve-dim)';
  }
}

export function CorpPage() {
  const { corpId } = useParams<{ corpId: string }>();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<CorpProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!corpId) return;
    setLoading(true);
    setError('');
    api.corp(corpId)
      .then(setProfile)
      .catch(() => setError(`Corporation not found: ${corpId}`))
      .finally(() => setLoading(false));
  }, [corpId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[var(--eve-dim)] py-8">
        <span className="pulse-green text-[var(--eve-green)]">///</span>
        Analyzing corporation...
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate(-1)}
          className="text-xs text-[var(--eve-dim)] hover:text-[var(--eve-text)] transition-colors"
        >
          &larr; Back
        </button>
        <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-3">
          {error || 'Corporation not found'}
        </div>
      </div>
    );
  }

  const kr = (profile.kill_ratio * 100).toFixed(0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-xs text-[var(--eve-dim)] hover:text-[var(--eve-text)] transition-colors"
          >
            &larr; Back
          </button>
          <div>
            <h2 className="text-lg font-bold text-[var(--eve-text)]">
              {profile.tribe_name || profile.corp_id.slice(0, 16)}
              {profile.tribe_short && (
                <span className="text-sm text-[var(--eve-dim)] ml-2">[{profile.tribe_short}]</span>
              )}
            </h2>
            <div className="text-xs text-[var(--eve-dim)] font-mono">{profile.corp_id}</div>
          </div>
        </div>
        <span
          className="text-xs font-bold uppercase px-2 py-1 rounded border"
          style={{ color: threatColor(profile.threat_level), borderColor: threatColor(profile.threat_level) }}
        >
          {profile.threat_level}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-[var(--eve-text)]">{profile.member_count}</div>
          <div className="text-xs text-[var(--eve-dim)]">Members</div>
          <div className="text-[10px] text-[var(--eve-dim)]">{profile.active_members} active</div>
        </div>
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-[var(--eve-red)]">{profile.total_kills}</div>
          <div className="text-xs text-[var(--eve-dim)]">Kills</div>
        </div>
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-[var(--eve-text)]">{profile.total_deaths}</div>
          <div className="text-xs text-[var(--eve-dim)]">Deaths</div>
        </div>
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 text-center">
          <div className="text-2xl font-bold" style={{ color: threatColor(profile.threat_level) }}>
            {kr}%
          </div>
          <div className="text-xs text-[var(--eve-dim)]">Kill Ratio</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top Killers */}
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
            Top Killers
          </h3>
          {profile.top_killers.length === 0 ? (
            <div className="text-xs text-[var(--eve-dim)]">No combat data.</div>
          ) : (
            <div className="space-y-1">
              {profile.top_killers.map((k, i) => (
                <div
                  key={k.entity_id}
                  className="flex items-center justify-between bg-[var(--eve-bg)] rounded px-3 py-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-[var(--eve-dim)] w-4">{i + 1}</span>
                    <Link
                      to={`/entity/${k.entity_id}`}
                      className="text-sm text-[var(--eve-green)] hover:underline"
                    >
                      {k.display_name || k.entity_id.slice(0, 12)}
                    </Link>
                  </div>
                  <span className="text-xs font-bold text-[var(--eve-red)]">{k.kills} kills</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Systems */}
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-blue,#3B82F6)] font-bold">
            Active Systems ({profile.system_count})
          </h3>
          {profile.systems.length === 0 ? (
            <div className="text-xs text-[var(--eve-dim)]">No system data.</div>
          ) : (
            <div className="space-y-1">
              {profile.systems.map((sys) => (
                <Link
                  key={sys}
                  to={`/system/${sys}`}
                  className="block bg-[var(--eve-bg)] rounded px-3 py-2 text-sm text-[var(--eve-text)]
                             hover:text-[var(--eve-green)] transition-colors"
                >
                  {sys}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
