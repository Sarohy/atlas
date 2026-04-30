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
  brentConsecutiveBelow95Count: number = 0,
  geopoliticalState: string | null = null,
  brentPrice: number | null = null,
): Promise<TrancheSizingResponse> {
  const params = new URLSearchParams({
    initial_catalyst: initialCatalyst,
    regime_rule: regimeRule,
    brent_consecutive_below_95_count: String(brentConsecutiveBelow95Count),
  });
  if (iranResolution !== null) {
    params.set('iran_resolution', iranResolution);
  }
  if (geopoliticalState !== null) {
    params.set('geopolitical_state', geopoliticalState);
  }
  if (brentPrice !== null) {
    params.set('brent_price', String(brentPrice));
  }
  return apiFetch(
    `/api/v1/tranche-sizing/${encodeURIComponent(ticker.toUpperCase())}?${params.toString()}`,
    trancheSizingResponseSchema,
  );
}

/**
 * Confirm an auto-triggered tranche deployment order (Framework 17).
 *
 * POST /api/v1/tranche-sizing/{ticker}/confirm-t2  or  confirm-t3.
 * Returns void (204 No Content). Call this when the operator clicks [Confirm]
 * in the auto-trigger modal.
 */
export async function confirmTranche(
  ticker: string,
  tranche: 't2' | 't3',
): Promise<void> {
  const url = `/api/v1/tranche-sizing/${encodeURIComponent(ticker.toUpperCase())}/confirm-${tranche}`;
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}${url}`,
    { method: 'POST' },
  );
  if (!response.ok) {
    throw new Error(`Failed to confirm ${tranche.toUpperCase()} tranche: ${response.status}`);
  }
}
