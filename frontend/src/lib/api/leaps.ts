import { apiFetch } from '@/lib/api/client';
import {
  leapsBucketStatusSchema,
  leapsEligibilitySchema,
  leapsPositionSchema,
  type LeapsBucketStatus,
  type LeapsEligibility,
  type LeapsPosition,
} from '@/lib/schemas/leaps';
import { z } from 'zod';

/**
 * Fetch LEAPS eligibility for a specific ticker.
 * Calls GET /api/v1/leaps/eligibility/{ticker}.
 * Pass the optional `score` to sync with the F1-panel score and avoid
 * a 1-point rounding divergence from independent re-computation.
 */
export function fetchLeapsEligibility(
  ticker: string,
  score?: number,
): Promise<LeapsEligibility> {
  const base = `/api/v1/leaps/eligibility/${encodeURIComponent(ticker.toUpperCase())}`;
  const url = score !== undefined ? `${base}?score=${score}` : base;
  return apiFetch(url, leapsEligibilitySchema);
}

/**
 * Fetch all open LEAPS positions.
 * Calls GET /api/v1/leaps/positions.
 */
export function fetchLeapsPositions(): Promise<LeapsPosition[]> {
  return apiFetch('/api/v1/leaps/positions', z.array(leapsPositionSchema));
}

/**
 * Fetch the current LEAPS bucket utilisation.
 * Calls GET /api/v1/leaps/bucket.
 */
export function fetchLeapsBucket(): Promise<LeapsBucketStatus> {
  return apiFetch('/api/v1/leaps/bucket', leapsBucketStatusSchema);
}

/**
 * Invalidate LEAPS eligibility cache for a ticker and re-evaluate.
 * Calls POST /api/v1/leaps/refresh/{ticker}.
 */
export function refreshLeapsEligibility(ticker: string): Promise<LeapsEligibility> {
  return apiFetch(
    `/api/v1/leaps/refresh/${encodeURIComponent(ticker.toUpperCase())}`,
    leapsEligibilitySchema,
    { method: 'POST' },
  );
}
