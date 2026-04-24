import { apiFetch } from '@/lib/api/client';
import {
  activeCyclesSummarySchema,
  section16ResultSchema,
  type ActiveCyclesSummary,
  type GrokScoreRequest,
  type OverrideRequest,
  type ResolveGapDownRequest,
  type Section16Result,
} from '@/lib/schemas/section16';

/**
 * Fetch the full Section 16 exit rules evaluation for one ticker.
 * Calls GET /api/v1/section16/exit-status/{ticker}.
 */
export function fetchSection16(ticker: string): Promise<Section16Result> {
  return apiFetch(
    `/api/v1/section16/exit-status/${encodeURIComponent(ticker)}`,
    section16ResultSchema,
  );
}

/**
 * Fetch all tickers with active (non-CLEAR) exit rule cycles.
 * Calls GET /api/v1/section16/active-cycles.
 */
export function fetchSection16ActiveCycles(): Promise<ActiveCyclesSummary> {
  return apiFetch(
    '/api/v1/section16/active-cycles',
    activeCyclesSummarySchema,
  );
}

/**
 * Apply a human override for a ticker (suppresses all exit signals).
 * Calls POST /api/v1/section16/override/{ticker}.
 */
export async function setSection16Override(
  ticker: string,
  body: OverrideRequest,
): Promise<{ ok: boolean }> {
  const resp = await fetch(
    `/api/v1/section16/override/${encodeURIComponent(ticker)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Override failed: ${resp.status} ${text}`);
  }
  return resp.json() as Promise<{ ok: boolean }>;
}

/**
 * Enter a Grok conviction score for a ticker.
 * Calls POST /api/v1/section16/grok-score/{ticker}.
 */
export async function enterGrokScore(
  ticker: string,
  body: GrokScoreRequest,
): Promise<{ ok: boolean }> {
  const resp = await fetch(
    `/api/v1/section16/grok-score/${encodeURIComponent(ticker)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Grok score entry failed: ${resp.status} ${text}`);
  }
  return resp.json() as Promise<{ ok: boolean }>;
}

/**
 * Mark a gap-down event as resolved.
 * Calls PUT /api/v1/section16/gap-down/{eventId}/resolve.
 */
export async function resolveGapDown(
  eventId: number,
  body: ResolveGapDownRequest,
): Promise<{ ok: boolean }> {
  const resp = await fetch(
    `/api/v1/section16/gap-down/${eventId}/resolve`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Resolve gap-down failed: ${resp.status} ${text}`);
  }
  return resp.json() as Promise<{ ok: boolean }>;
}
