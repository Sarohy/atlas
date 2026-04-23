import { apiFetch } from '@/lib/api/client';
import {
  framework30DrawdownStateSchema,
  framework30ResultSchema,
  type Framework30DrawdownState,
  type Framework30Result,
} from '@/lib/schemas/framework30';

/**
 * Fetch the full Framework 30 drawdown evaluation.
 * Calls GET /api/v1/framework30/drawdown.
 */
export function fetchFramework30Drawdown(): Promise<Framework30Result> {
  return apiFetch('/api/v1/framework30/drawdown', framework30ResultSchema);
}

/**
 * Fetch the lightweight Framework 30 drawdown state from backend cache.
 * Calls GET /api/v1/framework30/drawdown/state.
 */
export function fetchFramework30DrawdownState(): Promise<Framework30DrawdownState> {
  return apiFetch(
    '/api/v1/framework30/drawdown/state',
    framework30DrawdownStateSchema,
  );
}

/**
 * Invalidate backend cache and re-evaluate drawdown with fresh prices.
 * Calls POST /api/v1/framework30/refresh.
 */
export function refreshFramework30(): Promise<Framework30Result> {
  return apiFetch('/api/v1/framework30/refresh', framework30ResultSchema, {
    method: 'POST',
  });
}
