import { useNavigate } from 'react-router';

export function NexusCard() {
  const navigate = useNavigate();

  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-blue,#3B82F6)] rounded-lg p-4 space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-bold text-[var(--eve-blue,#3B82F6)] uppercase tracking-wider">
          NEXUS — Builder Webhook API
        </h3>
        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border
                         text-[var(--eve-green)] border-[var(--eve-green)]">
          Hackathon Open
        </span>
      </div>

      <p className="text-xs text-[var(--eve-dim)]">
        Subscribe to enriched event webhooks. WatchTower POSTs HMAC-signed payloads
        with resolved names, system data, and intelligence when matching on-chain
        events are indexed.
      </p>

      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div className="border border-[var(--eve-border)] rounded px-2 py-1.5 space-y-0.5">
          <div className="text-[var(--eve-dim)] uppercase">Events</div>
          <div className="text-[var(--eve-text)]">Killmails, Gate Transits</div>
        </div>
        <div className="border border-[var(--eve-border)] rounded px-2 py-1.5 space-y-0.5">
          <div className="text-[var(--eve-dim)] uppercase">Delivery</div>
          <div className="text-[var(--eve-text)]">HMAC-SHA256 signed POST</div>
        </div>
        <div className="border border-[var(--eve-border)] rounded px-2 py-1.5 space-y-0.5">
          <div className="text-[var(--eve-dim)] uppercase">Filters</div>
          <div className="text-[var(--eve-text)]">Entity, System, Type, Severity</div>
        </div>
        <div className="border border-[var(--eve-border)] rounded px-2 py-1.5 space-y-0.5">
          <div className="text-[var(--eve-dim)] uppercase">Hackathon Limits</div>
          <div className="text-[var(--eve-text)]">10 subs / 1,000 deliveries per day</div>
        </div>
      </div>

      <div className="border border-[var(--eve-border)] rounded p-2 text-[10px] font-mono text-[var(--eve-dim)] overflow-x-auto">
        <div className="text-[var(--eve-blue,#3B82F6)] mb-1">// Example payload</div>
        <div>{'{'}</div>
        <div className="ml-2">"event_type": "killmail",</div>
        <div className="ml-2">"victim_name": "PilotAlpha",</div>
        <div className="ml-2">"solar_system_name": "J-RXYN",</div>
        <div className="ml-2">"severity": "critical",</div>
        <div className="ml-2">"_nexus": {'{'} "enriched_at": ..., "version": 1 {'}'}</div>
        <div>{'}'}</div>
      </div>

      <button
        onClick={() => navigate('/account#nexus')}
        className="w-full px-3 py-2 text-xs font-bold border border-[var(--eve-blue,#3B82F6)]
                   text-[var(--eve-blue,#3B82F6)] rounded hover:bg-[var(--eve-blue,#3B82F6)]
                   hover:text-[var(--eve-bg)] transition-colors"
      >
        Set Up Webhook Subscription
      </button>
    </div>
  );
}
