'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchWashoutReference } from '@/lib/api/washout-reference';

/** Query key for the washout reference (config + exceptions). */
export const washoutReferenceKey = () => ['washout-reference'] as const;

/**
 * React Query hook for the Extension & Washout Overlay reference — the editable
 * thresholds (§10) and per-name risk exceptions. Config is near-static, so this
 * is cached for a long staleTime.
 */
export function useWashoutReference() {
  return useQuery({
    queryKey: washoutReferenceKey(),
    queryFn: fetchWashoutReference,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
