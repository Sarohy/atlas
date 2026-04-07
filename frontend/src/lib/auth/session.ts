'use client';

export const AUTH_SESSION_STORAGE_KEY = 'atlas.auth.session';
export const AUTH_SESSION_CHANGED_EVENT = 'atlas-auth-session-changed';

// Thirty minutes of inactivity is the required automatic sign-out window.
export const AUTH_SESSION_TIMEOUT_MS = 30 * 60 * 1000;

// Check once per minute to keep timer work small while staying responsive.
export const AUTH_SESSION_CHECK_INTERVAL_MS = 60 * 1000;

export type AuthSession = {
  email: string;
  expiresAt: string;
  lastActivityAt: string;
  rememberMe: boolean;
};

function isBrowserEnvironment() {
  return typeof window !== 'undefined';
}

function isAuthSession(value: unknown): value is AuthSession {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate['email'] === 'string' &&
    typeof candidate['expiresAt'] === 'string' &&
    typeof candidate['lastActivityAt'] === 'string' &&
    typeof candidate['rememberMe'] === 'boolean'
  );
}

export function dispatchAuthSessionChanged() {
  if (!isBrowserEnvironment()) {
    return;
  }

  window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
}

export function createAuthSession(
  email: string,
  rememberMe: boolean,
  now = new Date(),
): AuthSession {
  const nowIsoString = now.toISOString();

  return {
    email,
    expiresAt: new Date(now.getTime() + AUTH_SESSION_TIMEOUT_MS).toISOString(),
    lastActivityAt: nowIsoString,
    rememberMe,
  };
}

export function readAuthSession(): AuthSession | null {
  if (!isBrowserEnvironment()) {
    return null;
  }

  const serializedSession = window.localStorage.getItem(AUTH_SESSION_STORAGE_KEY);
  if (serializedSession === null) {
    return null;
  }

  try {
    const parsedValue: unknown = JSON.parse(serializedSession);
    return isAuthSession(parsedValue) ? parsedValue : null;
  } catch {
    return null;
  }
}

export function persistAuthSession(session: AuthSession) {
  if (!isBrowserEnvironment()) {
    return;
  }

  window.localStorage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session));
  dispatchAuthSessionChanged();
}

export function clearAuthSession() {
  if (!isBrowserEnvironment()) {
    return;
  }

  window.localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
  dispatchAuthSessionChanged();
}

export function isAuthSessionExpired(session: AuthSession, now = new Date()) {
  return new Date(session.expiresAt).getTime() <= now.getTime();
}

export function touchAuthSession(session: AuthSession, now = new Date()): AuthSession {
  return createAuthSession(session.email, session.rememberMe, now);
}
