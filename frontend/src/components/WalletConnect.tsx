import { ConnectButton } from '@mysten/dapp-kit';
import { useAuth, TIER_LABELS } from '../contexts/AuthContext';

export function WalletConnect() {
  const { wallet, subscription, isAdmin, disconnect } = useAuth();

  if (!wallet) {
    return (
      <div className="flex items-center gap-2">
        <ConnectButton
          connectText="Connect"
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold
                     border border-[var(--eve-green)] text-[var(--eve-green)]
                     rounded hover:bg-[var(--eve-green)] hover:text-[var(--eve-bg)]
                     transition-colors"
        />
      </div>
    );
  }

  const tier = TIER_LABELS[subscription?.tier ?? 0] || TIER_LABELS[0];
  const shortAddr = `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;

  return (
    <div className="flex items-center gap-3">
      {/* Admin badge */}
      {isAdmin && (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border
                     text-[var(--eve-red)] border-[var(--eve-red)]"
        >
          Admin
        </span>
      )}

      {/* Tier badge */}
      {subscription && (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border"
          style={{ color: tier.color, borderColor: tier.color }}
        >
          {tier.name}
        </span>
      )}

      {/* Wallet address */}
      <button
        onClick={disconnect}
        className="flex items-center gap-2 text-xs text-[var(--eve-text)]
                   hover:text-[var(--eve-green)] transition-colors"
        title="Click to disconnect wallet"
      >
        <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
        {shortAddr}
      </button>
    </div>
  );
}
