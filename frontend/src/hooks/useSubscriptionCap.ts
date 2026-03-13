import { useEffect, useState } from 'react';
import { useSuiClient } from '@mysten/dapp-kit';

const WATCHTOWER_PACKAGE = '0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca';
const SUB_CAP_TYPE = `${WATCHTOWER_PACKAGE}::subscription::SubscriptionCap`;

export interface SubscriptionCapData {
  objectId: string;
  tier: number;
  expiresAtMs: number;
  isActive: boolean;
}

export function useSubscriptionCap(walletAddress: string | null) {
  const client = useSuiClient();
  const [cap, setCap] = useState<SubscriptionCapData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!walletAddress) {
      setCap(null);
      return;
    }

    let cancelled = false;
    setLoading(true);

    client.getOwnedObjects({
      owner: walletAddress,
      filter: { StructType: SUB_CAP_TYPE },
      options: { showContent: true },
    }).then((res) => {
      if (cancelled) return;

      const now = Date.now();
      let best: SubscriptionCapData | null = null;

      for (const obj of res.data) {
        const content = obj.data?.content;
        if (content?.dataType !== 'moveObject') continue;

        const fields = content.fields as Record<string, string>;
        const tier = parseInt(fields.tier, 10);
        const expiresAtMs = parseInt(fields.expires_at_ms, 10);
        const isActive = expiresAtMs > now;

        // Pick highest active tier, or any if none active
        if (!best || (isActive && (!best.isActive || tier > best.tier))) {
          best = {
            objectId: obj.data!.objectId,
            tier,
            expiresAtMs,
            isActive,
          };
        }
      }

      setCap(best);
    }).catch(() => {
      if (!cancelled) setCap(null);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [walletAddress, client]);

  const refetch = () => {
    if (!walletAddress) return;
    setLoading(true);
    client.getOwnedObjects({
      owner: walletAddress,
      filter: { StructType: SUB_CAP_TYPE },
      options: { showContent: true },
    }).then((res) => {
      const now = Date.now();
      let best: SubscriptionCapData | null = null;
      for (const obj of res.data) {
        const content = obj.data?.content;
        if (content?.dataType !== 'moveObject') continue;
        const fields = content.fields as Record<string, string>;
        const tier = parseInt(fields.tier, 10);
        const expiresAtMs = parseInt(fields.expires_at_ms, 10);
        const isActive = expiresAtMs > now;
        if (!best || (isActive && (!best.isActive || tier > best.tier))) {
          best = { objectId: obj.data!.objectId, tier, expiresAtMs, isActive };
        }
      }
      setCap(best);
    }).catch(() => setCap(null))
      .finally(() => setLoading(false));
  };

  return { cap, loading, refetch };
}
