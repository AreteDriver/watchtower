import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api } from '../api';
import type { Fingerprint } from '../api';
import { FingerprintCard } from './FingerprintCard';
import { ActivityHeatmap } from './ActivityHeatmap';
import { EntityTimeline } from './EntityTimeline';
import { NarrativePanel } from './NarrativePanel';
import { ReputationBadge } from './ReputationBadge';
import { StreakTracker } from './StreakTracker';
import { TierGate } from './TierGate';
import { ErrorBoundary } from './ErrorBoundary';

export function EntityPage() {
  const { entityId } = useParams<{ entityId: string }>();
  const navigate = useNavigate();
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!entityId) return;
    setLoading(true);
    setError('');
    api.fingerprint(entityId)
      .then(setFingerprint)
      .catch(() => {
        setError(`Entity not found: ${entityId}`);
        setFingerprint(null);
      })
      .finally(() => setLoading(false));
  }, [entityId]);

  if (!entityId) {
    navigate('/');
    return null;
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[var(--eve-dim)] py-8">
        <span className="pulse-green text-[var(--eve-green)]">///</span>
        Analyzing entity...
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
          {error}
        </div>
        <button
          onClick={() => navigate('/')}
          className="text-xs text-[var(--eve-green)] hover:underline"
        >
          Back to search
        </button>
      </div>
    );
  }

  if (!fingerprint) return null;

  return (
    <div className="space-y-6">
      {/* Entity header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <button
            onClick={() => navigate('/')}
            className="text-xs text-[var(--eve-dim)] hover:text-[var(--eve-green)] mb-1"
          >
            &larr; Back
          </button>
          <h2 className="text-lg font-bold text-[var(--eve-text)]">
            <span className="text-[var(--eve-green)]">{entityId}</span>
            <span className="text-[var(--eve-dim)] text-sm ml-2">
              {fingerprint.entity_type} / {fingerprint.event_count} events
            </span>
          </h2>
        </div>
        <div className="text-xs text-[var(--eve-dim)]">
          OPSEC: <span className={
            fingerprint.opsec_score >= 70 ? 'text-[var(--eve-green)]' :
            fingerprint.opsec_score >= 40 ? 'text-[var(--eve-yellow,#FFCC00)]' :
            'text-[var(--eve-red)]'
          }>{fingerprint.opsec_score}/100 ({fingerprint.opsec_rating})</span>
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ErrorBoundary>
            <TierGate requiredTier={1} featureName="Behavioral Fingerprint">
              <FingerprintCard fp={fingerprint} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
              <ActivityHeatmap entityId={entityId} />
              <EntityTimeline entityId={entityId} />
            </div>
          </ErrorBoundary>
        </div>

        <div className="space-y-6">
          <ErrorBoundary>
            <TierGate requiredTier={1} featureName="Reputation Score">
              <ReputationBadge entityId={entityId} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <TierGate requiredTier={2} featureName="AI Narrative">
              <NarrativePanel entityId={entityId} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <StreakTracker entityId={entityId} />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
