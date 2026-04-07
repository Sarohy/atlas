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
