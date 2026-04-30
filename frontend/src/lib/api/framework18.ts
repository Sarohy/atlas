import { apiFetch } from '@/lib/api/client';
import {
  framework18ResultSchema,
  framework18SimpleResultSchema,
  type Framework18Result,
  type Framework18SimpleResult,
} from '@/lib/schemas/framework18';

/**
 * Fetch the full Framework 18 status (15-min cache on the backend).
 * Includes SPY weekly closes, candle dates, actions, and Factor 9 impact.
 */
export function fetchFramework18Status(): Promise<Framework18Result> {
  return apiFetch('/api/v1/framework18/status', framework18ResultSchema);
}

/**
 * Fetch the lightweight Framework 18 status.
 * Used by consuming framework cards that need only the gate state, not SPY data.
 */
export function fetchFramework18Simple(): Promise<Framework18SimpleResult> {
  return apiFetch('/api/v1/framework18/status/simple', framework18SimpleResultSchema);
}

/**
 * Force cache invalidation and re-fetch from Polygon.io.
 * Use after a new weekly candle closes (Friday 16:00 ET) if TTL has not expired.
 */
export function refreshFramework18(): Promise<Framework18Result> {
  return apiFetch('/api/v1/framework18/refresh', framework18ResultSchema, { method: 'POST' });
}
