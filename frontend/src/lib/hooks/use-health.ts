import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '@/lib/api/health';
import { type HealthResponse } from '@/lib/schemas/health';

export function useHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });
}
