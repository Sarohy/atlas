import { apiFetch } from '@/lib/api/client';
import {
  framework29GateStatusSchema,
  framework29ResultSchema,
  type Framework29GateStatus,
  type Framework29Result,
} from '@/lib/schemas/framework29';

/**
 * Fetch the full Framework 29 evaluation (all 5 signals + gate status).
 * Calls GET /api/v1/framework29/signals.
 */
export function fetchFramework29Signals(): Promise<Framework29Result> {
  return apiFetch('/api/v1/framework29/signals', framework29ResultSchema);
}

/**
 * Fetch the lightweight Framework 29 gate status from backend cache.
 * Calls GET /api/v1/framework29/signals/status.
 */
export function fetchFramework29Status(): Promise<Framework29GateStatus> {
  return apiFetch('/api/v1/framework29/signals/status', framework29GateStatusSchema);
}

/**
 * Submit a manual confirmation for Signal 4 (institutional ETF flow).
 * Calls POST /api/v1/framework29/signals/confirm.
 */
export function confirmSignal4(
  confirmed: boolean,
  reason: string,
): Promise<Record<string, unknown>> {
  return confirmSignal(4, confirmed, reason);
}

export function confirmSignal(
  signal: number,
  confirmed: boolean,
  reason: string,
): Promise<Record<string, unknown>> {
  return apiFetch(
    '/api/v1/framework29/signals/confirm',
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic response
    {} as any,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signal, confirmed, reason }),
    },
  );
}

/**
 * Invalidate backend cache and re-evaluate all 5 signals.
 * Calls POST /api/v1/framework29/refresh.
 */
export function refreshFramework29(): Promise<Framework29Result> {
  return apiFetch('/api/v1/framework29/refresh', framework29ResultSchema, {
    method: 'POST',
  });
}
