import { ChainIntegrity } from './ChainIntegrity';

const STATS: { value: string; label: string }[] = [
  { value: '17', label: 'DETECTION RULES' },
  { value: '4', label: 'CHECKER MODULES' },
  { value: 'CRITICAL \u2192 LOW', label: 'SEVERITY SCALE' },
];

const TAGS: { label: string; variant: 'live' | 'default' }[] = [
  { label: 'LIVE', variant: 'live' },
  { label: 'SUI / MOVE', variant: 'default' },
  { label: 'FASTAPI', variant: 'default' },
  { label: 'DISCORD ALERTS', variant: 'default' },
];

export function AegisEcosystem() {
  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

        @keyframes aegis-scan {
          0% { top: -4px; opacity: 0; }
          5% { opacity: 1; }
          95% { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }

        .aegis-card {
          font-family: 'Rajdhani', sans-serif;
        }

        .aegis-mono {
          font-family: 'Share Tech Mono', monospace;
        }

        .aegis-scan-container {
          position: relative;
          overflow: hidden;
        }

        .aegis-scan-container::after {
          content: '';
          position: absolute;
          top: -4px;
          left: 0;
          right: 0;
          height: 2px;
          background: linear-gradient(90deg, transparent, #7F77DD, transparent);
          animation: aegis-scan 4s ease-in-out infinite;
          pointer-events: none;
        }
      `}</style>

      <section className="aegis-card">
        {/* Section Header */}
        <div className="flex items-center gap-3 mb-4">
          <span
            className="aegis-mono text-xs tracking-[0.2em] font-bold"
            style={{ color: '#CCC9F8' }}
          >
            AEGIS STACK
          </span>
          <div className="flex-1 h-px" style={{ background: '#534AB7' }} />
          <span
            className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
            style={{
              color: '#CCC9F8',
              borderColor: '#534AB7',
              background: '#26215C',
            }}
          >
            CLEARANCE: PUBLIC
          </span>
        </div>

        {/* Dossier Card */}
        <div
          className="aegis-scan-container rounded-lg p-4"
          style={{
            background: 'var(--eve-surface)',
            borderLeft: '2px solid #7F77DD',
            border: '1px solid var(--eve-border)',
            borderLeftWidth: '2px',
            borderLeftColor: '#7F77DD',
          }}
        >
          {/* Designation */}
          <div className="mb-1">
            <span className="aegis-mono text-[var(--eve-dim)] text-xs">
              DESIGNATION
            </span>
          </div>
          <h3
            className="aegis-mono text-lg tracking-wider mb-0.5"
            style={{ color: '#CCC9F8' }}
          >
            // MONOLITH
          </h3>
          <p
            className="text-xs tracking-[0.15em] font-semibold mb-3"
            style={{ color: '#7F77DD' }}
          >
            BLOCKCHAIN INTEGRITY MONITOR
          </p>

          {/* Clearance Badge */}
          <div className="mb-4">
            <span
              className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
              style={{
                color: '#CCC9F8',
                borderColor: '#534AB7',
                background: '#26215C',
              }}
            >
              AEGIS-02 / ACTIVE
            </span>
          </div>

          {/* Summary */}
          <p className="text-sm leading-relaxed text-[var(--eve-text)] mb-5 max-w-2xl">
            Continuous chain surveillance for EVE Frontier on Sui. Detects state
            anomalies &mdash; orphaned objects, duplicate transactions, economic
            discrepancies &mdash; and generates structured bug reports with on-chain
            evidence. QA infrastructure for the Sui migration.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            {STATS.map((stat) => (
              <div
                key={stat.label}
                className="text-center py-2 rounded"
                style={{ background: 'rgba(127, 119, 221, 0.08)' }}
              >
                <div
                  className="aegis-mono text-base font-bold"
                  style={{ color: '#CCC9F8' }}
                >
                  {stat.value}
                </div>
                <div className="text-[10px] text-[var(--eve-dim)] tracking-wider font-semibold">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-2 mb-4">
            {TAGS.map((tag) => (
              <span
                key={tag.label}
                className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
                style={
                  tag.variant === 'live'
                    ? {
                        color: '#9FE1CB',
                        borderColor: '#1D9E75',
                        background: '#04342C',
                      }
                    : {
                        color: 'var(--eve-dim)',
                        borderColor: 'var(--eve-border)',
                        background: 'transparent',
                      }
                }
              >
                {tag.label}
              </span>
            ))}
          </div>

          {/* Access Link */}
          <div className="flex items-center gap-2">
            <span className="text-[var(--eve-dim)] text-xs">ACCESS</span>
            <a
              href="https://github.com/AreteDriver/monolith"
              target="_blank"
              rel="noopener noreferrer"
              className="aegis-mono text-xs hover:underline"
              style={{ color: '#7F77DD' }}
            >
              github.com/AreteDriver/monolith &rarr;
            </a>
          </div>
        </div>

        {/* Live Chain Integrity Feed from Monolith */}
        <div className="mt-4">
          <ChainIntegrity />
        </div>
      </section>
    </>
  );
}
