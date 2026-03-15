/**
 * WatchTower API client — browser implementation.
 * Types imported from @watchtower/api-client (shared with mobile).
 */

// Re-export all types so existing component imports don't break
export type {
  Entity, Fingerprint, TimelineEvent, CompareResult, Narrative,
  FeedItem, Dossier, SearchResult, KillGraphData, HotzoneData,
  StreakData, CorpData, CorpProfile, CorpRivalry, ReputationData,
  AssemblyData, AssemblyStats, SystemDossier, SubscriptionData,
  WatchData, AlertData, NexusSubscription, NexusSubscribeResponse,
  NexusQuota, NexusDelivery, WalletConnectResponse, WalletMeResponse,
  CycleEnvelope, CycleInfo, OrbitalZone, ScanResult, Clone,
  CrownEntry, CrownRoster, AnalyticsData, PricingData,
  FeralAiEvent,
} from '@watchtower/api-client';

import { createClient } from '@watchtower/api-client';

const SESSION_KEY = 'watchtower_session';
const WALLET_KEY = 'watchtower_wallet';

export const api = createClient({
  baseUrl: '/api',
  getHeaders: () => {
    const headers: Record<string, string> = {};
    const session = localStorage.getItem(SESSION_KEY);
    if (session) headers['X-Session'] = session;
    const wallet = localStorage.getItem(WALLET_KEY);
    if (wallet) headers['X-Wallet-Address'] = wallet;
    return headers;
  },
});
