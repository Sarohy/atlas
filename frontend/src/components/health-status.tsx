'use client';

import { useHealth } from '@/lib/hooks/use-health';

export function HealthStatus() {
  const { data, isLoading, isError } = useHealth();

  if (isLoading) {
    return <span className="text-sm text-muted-foreground">Loading...</span>;
  }

  if (isError) {
    return <span className="text-sm text-destructive">Error: could not reach backend</span>;
  }

  return <span className="text-sm text-green-600">Backend: {data?.status}</span>;
}
