'use client';

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { signOut as signOutRequest } from '@/lib/api/auth';
import {
  AUTH_SESSION_CHANGED_EVENT,
  AUTH_SESSION_CHECK_INTERVAL_MS,
  clearAuthSession,
  createAuthSession,
  isAuthSessionExpired,
  persistAuthSession,
  readAuthSession,
  touchAuthSession,
  type AuthSession,
} from '@/lib/auth/session';

type AuthSessionContextValue = {
  isAuthenticated: boolean;
  isHydrated: boolean;
  session: AuthSession | null;
  signIn: (payload: { email: string; rememberMe: boolean }) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

const ACTIVITY_EVENTS = ['keydown', 'mousedown', 'mousemove', 'scroll', 'touchstart'] as const;

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const sessionRef = useRef<AuthSession | null>(null);

  useEffect(() => {
    const nextSession = readAuthSession();
    if (nextSession !== null && isAuthSessionExpired(nextSession)) {
      clearAuthSession();
      sessionRef.current = null;
      setSession(null);
    } else {
      sessionRef.current = nextSession;
      setSession(nextSession);
    }

    setIsHydrated(true);
  }, []);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    const syncFromStorage = () => {
      const nextSession = readAuthSession();
      if (nextSession !== null && isAuthSessionExpired(nextSession)) {
        clearAuthSession();
        sessionRef.current = null;
        setSession(null);
        return;
      }

      sessionRef.current = nextSession;
      setSession(nextSession);
    };

    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, syncFromStorage);
    window.addEventListener('storage', syncFromStorage);

    return () => {
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, syncFromStorage);
      window.removeEventListener('storage', syncFromStorage);
    };
  }, [isHydrated]);

  useEffect(() => {
    if (!isHydrated || session === null) {
      return;
    }

    const markActivity = () => {
      const currentSession = sessionRef.current;
      if (currentSession === null) {
        return;
      }

      const refreshedSession = touchAuthSession(currentSession);
      sessionRef.current = refreshedSession;
      persistAuthSession(refreshedSession);
      setSession(refreshedSession);
    };

    const intervalId = window.setInterval(() => {
      const currentSession = sessionRef.current;
      if (currentSession !== null && isAuthSessionExpired(currentSession)) {
        clearAuthSession();
        sessionRef.current = null;
        setSession(null);
      }
    }, AUTH_SESSION_CHECK_INTERVAL_MS);

    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, markActivity, { passive: true });
    });

    return () => {
      window.clearInterval(intervalId);
      ACTIVITY_EVENTS.forEach((eventName) => {
        window.removeEventListener(eventName, markActivity);
      });
    };
  }, [isHydrated, session]);

  async function signIn(payload: { email: string; rememberMe: boolean }) {
    const nextSession = createAuthSession(payload.email, payload.rememberMe);
    sessionRef.current = nextSession;
    persistAuthSession(nextSession);
    setSession(nextSession);
  }

  async function signOut() {
    try {
      await signOutRequest();
    } finally {
      clearAuthSession();
      sessionRef.current = null;
      setSession(null);
    }
  }

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      isAuthenticated: session !== null,
      isHydrated,
      session,
      signIn,
      signOut,
    }),
    [isHydrated, session],
  );

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}

export function useAuthSession() {
  const context = useContext(AuthSessionContext);

  if (context === null) {
    throw new Error('useAuthSession must be used within an AuthSessionProvider.');
  }

  return context;
}
