import { apiFetch } from '@/lib/api/client';
import {
  framework9ResultSchema,
  type Framework9Result,
} from '@/lib/schemas/framework9';

/**
 * Fetch the Framework 9 options flow evaluation for a single ticker.
 * Calls GET /api/v1/framework9/{ticker}.
 */
export function fetchFramework9(ticker: string): Promise<Framework9Result> {
  return apiFetch(
    `/api/v1/framework9/${encodeURIComponent(ticker.toUpperCase())}`,
    framework9ResultSchema,
  );
}

/**
 * Invalidate the backend in-memory cache for *ticker* and re-evaluate.
 * Calls POST /api/v1/framework9/{ticker}/refresh.
 */
export function refreshFramework9(ticker: string): Promise<Framework9Result> {
  return apiFetch(
    `/api/v1/framework9/${encodeURIComponent(ticker.toUpperCase())}/refresh`,
    framework9ResultSchema,
    { method: 'POST' },
  );
}
