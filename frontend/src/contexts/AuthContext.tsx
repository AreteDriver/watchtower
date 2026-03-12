import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { useCurrentAccount, useDisconnectWallet } from '@mysten/dapp-kit';
import { api } from '../api';
import type { SubscriptionData } from '../api';

export const TIER_LABELS: Record<number, { name: string; color: string }> = {
  0: { name: 'Free', color: 'var(--eve-dim)' },
  1: { name: 'Scout', color: 'var(--eve-blue)' },
  2: { name: 'Oracle', color: 'var(--eve-green)' },
  3: { name: 'Spymaster', color: 'var(--eve-orange)' },
};

const SESSION_KEY = 'watchtower_session';
const WALLET_KEY = 'watchtower_wallet';

interface AuthState {
  wallet: string | null;
  subscription: SubscriptionData | null;
  connecting: boolean;
  isAdmin: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  refreshSubscription: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useState<string | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  const currentAccount = useCurrentAccount();
  const { mutate: disconnectWallet } = useDisconnectWallet();

  const fetchSubscription = useCallback(async (addr: string) => {
    try {
      const sub = await api.subscription(addr);
      setSubscription(sub);
    } catch {
      setSubscription(null);
    }
  }, []);

  // When Sui wallet connects/changes, register session with backend
  useEffect(() => {
    if (!currentAccount?.address) {
      // Wallet disconnected in dapp-kit but we may still have a session
      return;
    }

    const suiAddress = currentAccount.address;

    // Check if we already have a session for this wallet
    const savedWallet = localStorage.getItem(WALLET_KEY);
    const savedSession = localStorage.getItem(SESSION_KEY);
    if (savedWallet === suiAddress && savedSession) {
      // Already have a session, just restore state
      setWallet(suiAddress);
      // Verify session is still valid
      api.walletMe()
        .then((me) => {
          setIsAdmin(me.is_admin);
        })
        .catch(() => {
          // Session expired, re-register
          registerSession(suiAddress);
        });
      return;
    }

    // New connection — register with backend
    registerSession(suiAddress);
  }, [currentAccount?.address]);

  const registerSession = async (address: string) => {
    setConnecting(true);
    try {
      const result = await api.walletConnect(address);
      localStorage.setItem(SESSION_KEY, result.session_token);
      localStorage.setItem(WALLET_KEY, address);
      setWallet(address);
      setIsAdmin(result.is_admin);
    } catch {
      // Backend may be down, still show wallet as connected
      localStorage.setItem(WALLET_KEY, address);
      setWallet(address);
    }
    setConnecting(false);
  };

  // Fetch subscription when wallet changes
  useEffect(() => {
    if (!wallet) {
      setSubscription(null);
      return;
    }
    fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  // Restore session on mount (if dapp-kit hasn't connected yet)
  useEffect(() => {
    const savedSession = localStorage.getItem(SESSION_KEY);
    const savedWallet = localStorage.getItem(WALLET_KEY);
    if (savedSession && savedWallet && !currentAccount) {
      // We have a saved session but dapp-kit hasn't auto-connected yet
      // Verify session validity
      api.walletMe()
        .then((me) => {
          setWallet(me.wallet_address);
          setIsAdmin(me.is_admin);
        })
        .catch(() => {
          // Session invalid, clear
          localStorage.removeItem(SESSION_KEY);
          localStorage.removeItem(WALLET_KEY);
        });
    }
  }, []);

  // Handle wallet disconnect from dapp-kit
  useEffect(() => {
    if (currentAccount === null && wallet) {
      // dapp-kit reports no account but we have a wallet — user disconnected
      // Only clear if we previously had a currentAccount (not initial load)
    }
  }, [currentAccount, wallet]);

  const connect = useCallback(async () => {
    // This is a no-op now — connection is handled by dapp-kit ConnectButton
    // which triggers the useEffect above via useCurrentAccount()
  }, []);

  const disconnect = useCallback(() => {
    // Clear backend session
    api.walletDisconnect().catch(() => {});

    // Clear local state
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(WALLET_KEY);
    setWallet(null);
    setSubscription(null);
    setIsAdmin(false);

    // Disconnect dapp-kit wallet
    disconnectWallet();
  }, [disconnectWallet]);

  const refreshSubscription = useCallback(async () => {
    if (wallet) await fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  return (
    <AuthContext.Provider
      value={{
        wallet,
        subscription,
        connecting,
        isAdmin,
        connect,
        disconnect,
        refreshSubscription,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
