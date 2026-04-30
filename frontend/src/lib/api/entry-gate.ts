import { apiFetch } from '@/lib/api/client';
import { entryGateResultSchema, type EntryGateResult } from '@/lib/schemas/entry-gate';

const ENCODE = (ticker: string): string => encodeURIComponent(ticker.trim().toUpperCase());

/** GET /api/v1/entry-gate/{ticker} — unified Section 16 + Framework 12 in one call. */
export function fetchEntryGate(ticker: string): Promise<EntryGateResult> {
  return apiFetch(`/api/v1/entry-gate/${ENCODE(ticker)}`, entryGateResultSchema);
}
