'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthSession } from './auth-session-provider';

const DEFAULT_AUTHENTICATED_PATH = '/';
const SIGN_IN_PATH = '/auth/sign-in';

type AuthGateProps = {
  children: React.ReactNode;
};

function isSignInRoute(pathname: string) {
  return pathname.startsWith('/auth');
}

export function AuthGate({ children }: AuthGateProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isHydrated } = useAuthSession();

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    if (!isAuthenticated && !isSignInRoute(pathname)) {
      router.replace(SIGN_IN_PATH);
      return;
    }

    if (isAuthenticated && isSignInRoute(pathname)) {
      router.replace(DEFAULT_AUTHENTICATED_PATH);
    }
  }, [isAuthenticated, isHydrated, pathname, router]);

  if (!isHydrated) {
    return null;
  }

  if (!isAuthenticated && !isSignInRoute(pathname)) {
    return null;
  }

  if (isAuthenticated && isSignInRoute(pathname)) {
    return null;
  }

  return <>{children}</>;
}
