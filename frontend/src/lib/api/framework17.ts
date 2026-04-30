import { apiFetch } from '@/lib/api/client';
import {
  flagHistoryEntrySchema,
  framework17ResultSchema,
  framework17SimpleResultSchema,
  type FlagHistoryEntry,
  type Framework17Result,
  type Framework17SimpleResult,
  type SetFlagRequest,
} from '@/lib/schemas/framework17';
import { z } from 'zod';

/**
 * Fetch the full Framework 17 geopolitical monitor evaluation.
 * Calls GET /api/v1/framework17/status.
 * Cached 60 s on the backend.
 */
export function fetchFramework17Status(): Promise<Framework17Result> {
  return apiFetch('/api/v1/framework17/status', framework17ResultSchema);
}

/**
 * Fetch the lightweight F17 flag status.
 * Calls GET /api/v1/framework17/flag.
 */
export function fetchFramework17Flag(): Promise<Framework17SimpleResult> {
  return apiFetch('/api/v1/framework17/flag', framework17SimpleResultSchema);
}

/**
 * Fetch the last N days of geopolitical flag history.
 * Calls GET /api/v1/framework17/history?days={days}.
 */
export function fetchFramework17History(
  days: number = 30,
): Promise<FlagHistoryEntry[]> {
  return apiFetch(
    `/api/v1/framework17/history?days=${days}`,
    z.array(flagHistoryEntrySchema),
  );
}

/**
 * Set the geopolitical flag (operator only).
 * Calls POST /api/v1/framework17/flag.
 * Returns the fresh full evaluation after writing.
 */
export function setFramework17Flag(
  body: SetFlagRequest,
): Promise<Framework17Result> {
  return apiFetch('/api/v1/framework17/flag', framework17ResultSchema, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
