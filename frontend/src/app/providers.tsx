'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { AuthGate } from '@/components/auth/auth-gate';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            // Prevent score flicker: window-focus refetches + staleTime:0 on
            // heavy AV hooks would otherwise fire 7+ API calls per alt-tab,
            // causing intermittent rate-limit gaps that produce different scores
            // each time.  Data is still always fresh on component mount.
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthSessionProvider>
        <AuthGate>{children}</AuthGate>
      </AuthSessionProvider>
    </QueryClientProvider>
  );
}
