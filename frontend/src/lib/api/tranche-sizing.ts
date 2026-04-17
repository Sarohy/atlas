import { apiFetch } from '@/lib/api/client';
import {
  trancheSizingResponseSchema,
  type TrancheSizingResponse,
} from '@/lib/schemas/tranche-sizing';

/**
 * Fetch Framework 4 tranche-sizing data for a given ticker.
 *
 * Pass ``regimeRule`` from the UI's already-displayed Framework 2 value so
 * the backend doesn't re-fetch regime state independently — keeping F4 in
 * sync with what the investor is currently seeing in F2.
 */
export function fetchTrancheSizing(
  ticker: string,
  initialCatalyst: 'yes' | 'no',
  regimeRule: string = 'NORMAL',
  iranResolution: string | null = null,
): Promise<TrancheSizingResponse> {
  const params = new URLSearchParams({
    initial_catalyst: initialCatalyst,
    regime_rule: regimeRule,
  });
  if (iranResolution !== null) {
    params.set('iran_resolution', iranResolution);
  }
  return apiFetch(
    `/api/v1/tranche-sizing/${encodeURIComponent(ticker.toUpperCase())}?${params.toString()}`,
    trancheSizingResponseSchema,
  );
}
